import os
import warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')
import socket
import threading
import time
import logging
from collections import defaultdict, deque
import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()

class EnhancedDDoSDefender:
    def __init__(self, port=80):
        self.port = port
        self.running = True
        self.connections = defaultdict(lambda: {
            'timestamps': deque(maxlen=100),
            'bytes_received': deque(maxlen=100),
            'packet_sizes': deque(maxlen=100),
            'ports': set(),
            'request_types': defaultdict(int),
            'last_request': 0,
            'request_count': 0,
            'warning_count': 0
        })
        self.blocked_ips = set()
        self.suspicious_ips = set()
        self.attack_log = deque(maxlen=1000)
        self.thresholds = {
            'requests_per_second': 10,
            'concurrent_connections': 20,
            'min_request_interval': 0.1,
            'max_packet_size': 8192,
            'warning_threshold': 3,
            'suspicious_rate': 5,
            'block_duration': 300,
            'max_bandwidth_per_ip': 1024 * 1024
        }
        logging.basicConfig(
            filename='defender.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.metrics = {
            'total_connections': 0,
            'blocked_attacks': 0,
            'bytes_processed': 0,
            'current_bandwidth': 0,
            'suspicious_ips': 0
        }

    def check_rate_limit(self, ip):
        conn_data = self.connections[ip]
        current_time = time.time()
        if conn_data['last_request'] > 0:
            interval = current_time - conn_data['last_request']
            if interval < self.thresholds['min_request_interval']:
                return False
        recent_requests = len([t for t in conn_data['timestamps'] if current_time - t <= 1])
        if recent_requests > self.thresholds['requests_per_second']:
            return False
        conn_data['last_request'] = current_time
        return True

    def check_bandwidth_limit(self, ip, data_size):
        conn_data = self.connections[ip]
        current_time = time.time()
        recent_bytes = sum(b for b in conn_data['bytes_received'])
        if len(conn_data['timestamps']) > 1:
            time_window = conn_data['timestamps'][-1] - conn_data['timestamps'][0]
            if time_window > 0:
                current_bandwidth = recent_bytes / time_window
                return current_bandwidth <= self.thresholds['max_bandwidth_per_ip']
        return True

    def detect_attack_pattern(self, ip):
        conn_data = self.connections[ip]
        current_time = time.time()
        if len(conn_data['timestamps']) >= 3:
            intervals = np.diff([t for t in conn_data['timestamps']])
            if np.std(intervals) < 0.1:
                return True
            if len(intervals) > 5:
                rate_change = np.diff(intervals)
                if np.all(rate_change < 0):
                    return True
        if len(conn_data['packet_sizes']) > 5:
            sizes = list(conn_data['packet_sizes'])
            if np.std(sizes) < 1:
                return True
            if np.mean(sizes) > self.thresholds['max_packet_size']:
                return True
        return False

    def handle_connection(self, client_socket, address):
        ip = address[0]
        port = address[1]
        if ip in self.blocked_ips:
            client_socket.close()
            return
        conn_data = self.connections[ip]
        conn_data['timestamps'].append(time.time())
        conn_data['ports'].add(port)
        if len([c for c in conn_data['timestamps'] if time.time() - c < 1]) > self.thresholds['concurrent_connections']:
            self.warn_ip(ip, "Too many concurrent connections")
            client_socket.close()
            return
        try:
            while self.running:
                try:
                    data = client_socket.recv(self.thresholds['max_packet_size'])
                    if not data:
                        break
                    if not self.check_rate_limit(ip):
                        self.warn_ip(ip, "Rate limit exceeded")
                        break
                    if not self.check_bandwidth_limit(ip, len(data)):
                        self.warn_ip(ip, "Bandwidth limit exceeded")
                        break
                    conn_data['bytes_received'].append(len(data))
                    conn_data['packet_sizes'].append(len(data))
                    conn_data['request_count'] += 1
                    if self.detect_attack_pattern(ip):
                        self.warn_ip(ip, "Suspicious traffic pattern detected")
                        break
                    self.metrics['bytes_processed'] += len(data)
                except socket.timeout:
                    break
        except Exception as e:
            logging.error(f"Connection error from {ip}: {str(e)}")
        finally:
            client_socket.close()

    def warn_ip(self, ip, reason):
        conn_data = self.connections[ip]
        conn_data['warning_count'] += 1
        logging.warning(f"Warning {conn_data['warning_count']} for IP {ip}: {reason}")
        if conn_data['warning_count'] >= self.thresholds['warning_threshold']:
            self.block_ip(ip, reason)
        elif ip not in self.suspicious_ips:
            self.suspicious_ips.add(ip)
            self.metrics['suspicious_ips'] += 1

    def block_ip(self, ip, reason="Multiple warnings"):
        if ip not in self.blocked_ips:
            self.blocked_ips.add(ip)
            self.metrics['blocked_attacks'] += 1
            if ip in self.suspicious_ips:
                self.suspicious_ips.remove(ip)
                self.metrics['suspicious_ips'] -= 1
            self.attack_log.append({
                'time': time.time(),
                'ip': ip,
                'reason': reason,
                'connections': self.connections[ip]['request_count'],
                'bytes_received': sum(self.connections[ip]['bytes_received'])
            })
            logging.info(f"Blocked IP {ip}: {reason}")
            threading.Timer(self.thresholds['block_duration'], lambda: self.unblock_ip(ip)).start()

    def unblock_ip(self, ip):
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            del self.connections[ip]
            logging.info(f"Unblocked IP: {ip}")

    def start_defense(self):
        console.print("[green]Starting Enhanced DDoS Defense System...[/green]")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_socket.bind(('', self.port))
            server_socket.listen(5)
            threading.Thread(target=self.display_stats, daemon=True).start()
            console.print(f"[green]Defending port {self.port}...[/green]")
            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    client_socket.settimeout(30)
                    threading.Thread(target=self.handle_connection, args=(client_socket, address), daemon=True).start()
                except Exception as e:
                    logging.error(f"Connection accept error: {str(e)}")
        except Exception as e:
            logging.error(f"Server error: {str(e)}")
        finally:
            server_socket.close()

    def display_stats(self):
        while self.running:
            table = Table(title="Defense Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            table.add_row("Active Connections", str(self.metrics['total_connections']))
            table.add_row("Blocked IPs", str(len(self.blocked_ips)))
            table.add_row("Suspicious IPs", str(len(self.suspicious_ips)))
            table.add_row("Data Processed", f"{self.metrics['bytes_processed'] / 1024 / 1024:.2f} MB")
            console.clear()
            console.print(table)
            if self.attack_log:
                attack_table = Table(title="Recent Attacks")
                attack_table.add_column("Time")
                attack_table.add_column("IP")
                attack_table.add_column("Reason")
                attack_table.add_column("Connections")
                for attack in list(self.attack_log)[-5:]:
                    attack_table.add_row(
                        time.strftime('%H:%M:%S', time.localtime(attack['time'])),
                        attack['ip'],
                        attack['reason'],
                        str(attack['connections'])
                    )
                console.print(attack_table)
            time.sleep(1)

def main():
    console.print("[bold cyan]Enhanced DDoS Defense System[/bold cyan]")
    while True:
        try:
            port = int(console.input("[bold yellow]Enter port to protect: [/bold yellow]"))
            if 1 <= port <= 65535:
                break
            console.print("[red]Port must be between 1 and 65535.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a valid port number.[/red]")
    defender = EnhancedDDoSDefender(port=port)
    try:
        defender.start_defense()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down defender...[/yellow]")
        defender.running = False

if __name__ == "__main__":
    main()

