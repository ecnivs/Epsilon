# response handler
from dflow_handler import Agent
import spacy
import hashlib
import json
import os
import random

class ResponseHandler:
    def __init__(self):
        self.agent = Agent()
        self.nlp = spacy.load("en_core_web_sm")
        self.cache_file = "cache.json"
        self.cache = self.load_cache()

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

    def extract_key_phrases(self, query):
        doc = self.nlp(query)
        phrases = [chunk.text for chunk in doc.noun_chunks if any(token.pos_ in ['PROPN', 'NOUN'] for token in chunk)]
        return phrases

    def handle(self, query):
        query_hash = self.hash_query(query)
        agent_response = self.agent.get_response(query)
        response = None

        if agent_response is not None:
            if query_hash in self.cache:
                detected_intent = self.cache[query_hash]['intent']
                cached_responses = self.cache[detected_intent]
                if cached_responses:
                    return f'{random.choice(cached_responses)}'
            return "Request timed out. Please check your internet connection."

        if not response:
            response = self.agent.fulfillment_text

        detected_intent = self.agent.detected_intent
        if detected_intent not in self.cache:
            self.cache[detected_intent] = []

        if response not in self.cache[detected_intent]:
            self.cache[detected_intent].append(response)

        self.cache[query_hash] = {
            'intent': detected_intent
        }
        return response
