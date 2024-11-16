import re
from pygments.lexers import guess_lexer, ClassNotFound
from urllib.parse import urlparse
import requests
import time
import os
from dotenv import load_dotenv
import math
import hashlib
import json

load_dotenv()

class InputHandler:
    def __init__(self):
        self.vt_api_key = os.getenv('API_KEY')
        self.cache_file = "url_cache.json"
        self.cache = self.load_cache()

        self.malicious_patterns = [
            # javaScript patterns
            r'eval\s*\(.*\)',
            r'document\.write\s*\(.*\)',
            r'(atob|btoa)\s*\(.*\)',
            r'\\x[0-9a-fA-F]{2}',
            r'fromCharCode\s*\(',
            r'<script>[^<]*<\/script>',

            # python patterns
            r'exec\s*\(.*\)',
            r'eval\s*\(.*\)',
            r'subprocess\..*',
            r'os\.(system|popen|spawn)',
            r'__import__\s*\(.*\)',

            # shell command injection patterns
            r';\s*(rm|del|format)',
            r'>(>)?.*\.(sh|bat|exe)',

            # data exfiltration patterns
            r'new\s+WebSocket\s*\(',
            r'navigator\.sendBeacon\s*\(',
        ]

        self.malicious_regex = re.compile('|'.join(self.malicious_patterns), re.IGNORECASE)
        self.obfuscation_patterns = [
            r'\\u[0-9a-fA-F]{4}',
            r'\\x[0-9a-fA-F]{2}',
            r'\w{50,}',
            r'String\.fromCharCode',
            r'unescape\s*\(',
            r'\[([\'"]).*?\1\]\.join\(\s*[\'""]\s*\)'
        ]

        self.obfuscation_regex = re.compile('|'.join(self.obfuscation_patterns), re.IGNORECASE)

    def is_code(self, text):
        try:
            lexer = guess_lexer(text)
            return lexer.name
        except ClassNotFound:
            return "text only"

    def hash_query(self, query):
        return hashlib.sha256(query.encode()).hexdigest()

    def load_cache(self):
        if not os.path.exists(self.cache_file):
            with open(self.cache_file, 'w') as file:
                json.dump({}, file)
            return {}
        else:
            with open(self.cache_file, 'r') as file:
                return json.load(file)

    def save_cache(self):
        with open(self.cache_file, 'w') as file:
            json.dump(self.cache, file)

    def is_malicious_url(self, url):
        url_hash = self.hash_query(url)

        if url_hash in self.cache:
            print(f"Cache hit for {url}")
            return self.cache[url_hash]

        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return False

            scan_url = 'https://www.virustotal.com/vtapi/v2/url/scan'
            scan_params = {
                'apikey': self.vt_api_key,
                'url': url
            }

            scan_response = requests.post(scan_url, params=scan_params)
            if scan_response.status_code != 200:
                print(f"Scan submission error: {scan_response.status_code}")
                return False

            time.sleep(3)

            report_url = 'https://www.virustotal.com/vtapi/v2/url/report'
            report_params = {
                'apikey': self.vt_api_key,
                'resource': url
            }

            response = requests.get(report_url, params=report_params)
            result = response.json()

            if result.get('response_code', 0) == 0:
                print(f"URL not found in database: {result.get('verbose_msg')}")
                return False

            is_malicious = result.get('positives', 0) > 0

            self.cache[url_hash] = is_malicious
            self.save_cache()

            return is_malicious

        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            return False
        except ValueError as e:
            print(f"JSON Parsing Error: {e}")
            return False
        except Exception as e:
            print(f"General Error: {e}")
            return False

    def is_malicious_code(self, code):
        reasons = []

        malicious_matches = self.malicious_regex.findall(code)
        if malicious_matches:
            reasons.extend([f"Suspicious pattern found: {match}" for match in malicious_matches])

        obfuscation_matches = self.obfuscation_regex.findall(code)
        if obfuscation_matches:
            reasons.extend([f"Possible obfuscation technique: {match}" for match in obfuscation_matches])

        entropy = self._calculate_entropy(code)
        if entropy > 5.0:
            reasons.append(f"High entropy detected: {entropy:.2f}")

        return bool(reasons), reasons

    def _calculate_entropy(self, text):
        prob = [float(text.count(c)) / len(text) for c in set(text)]
        entropy = - sum(p * math.log(p) / math.log(2.0) for p in prob)
        return entropy

    def classify(self, text):
        url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        if url_pattern.match(text):
            if self.is_malicious_url(text):
                return "malicious_link"
            return "safe_link"

        lang = self.is_code(text)
        if lang != "text only":
            is_malicious, reasons = self.is_malicious_code(text)
            if is_malicious:
                return f"malicious_code ({lang}): {'; '.join(reasons)}"
            return f"safe_code ({lang})"

        return "text"

if __name__ == "__main__":
    input_handler = InputHandler()
    #test_url = "http://malware.wicar.org/data/js_crypto_miner.html"

    while True:
        query = input("$ ").strip()
        print(f"result for {query}\n ---> {input_handler.classify(query)}")
