# Luna
import os
from res_handler import ResponseHandler
import pyaudio
import json
import threading
from vosk import Model, KaldiRecognizer
import time
from TTS.api import TTS
import logging
import torch
import wave

logging.basicConfig(level=logging.DEBUG, 
                    format='%(levelname)s - %(message)s',
                    force=True)

class Core:
    def __init__(self, name):
        self.name = name
        self.model_path = 'vosk-model'
        self.threads = []
        self.query = None
        self.called = False
        self.call_words = ["hey", "okay", "hi", "hello", "yo", "listen", "attention", "are you there"]

        self.on_init()

    def on_init(self):
        self.lock = threading.Lock()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        self.shutdown_flag = threading.Event()
        self.audio = pyaudio.PyAudio()
        self.model = self.load_vosk_model()
        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.res_handler = ResponseHandler(self)

    def load_vosk_model(self):
        if not os.path.exists(self.model_path):
            logging.info(f'Model not found at {self.model_path}, please check the path.')
            exit(1)
        try:
            return Model(self.model_path)
        except ValueError as e:
            logging.error(f'Error loading Vosk model: {e}')
            exit(1)

    def speak(self, text):
        try:
            self.tts.tts_to_file(text,
                    file_path="audio/output.wav",
                    speaker_wav="audio/speaker.wav",
                    language="en")
            self.play_audio("output.wav")
        except Exception as e:
            logging.error(f'Error in TTS: {e}')

    def play_audio(self, filename):
        def audio_thread():
            stream = None
            try:
                with wave.open(f'audio/{filename}', 'rb') as wf:
                    chunk_size = 1024
                    stream = self.audio.open(
                        format=self.audio.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True,
                        frames_per_buffer=chunk_size)

                    data = wf.readframes(chunk_size)
                    while data:
                        while stream.get_write_available() < len(data):
                            time.sleep(0.001)
                        stream.write(data)
                        data = wf.readframes(chunk_size)

                    stream.stop_stream()

            except Exception as e:
                logging.error(f'Error playing audio file {filename}: {e}')
            finally:
                if stream is not None:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()

        threading.Thread(target=audio_thread, daemon=True).start()

    def recognize_speech(self):
        stream = self.audio.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        frames_per_buffer=4096)
        stream.start_stream()
        
        logging.info("Listening...")

        try:
            while not self.shutdown_flag.is_set():
                data = stream.read(4096, exception_on_overflow=False)
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    if 'text' in result and result['text'].strip() != "":
                        with self.lock:
                            self.query = result['text'].strip()
                        logging.info(f'Recognized: {self.query}')

                with self.lock:
                    if not self.query:
                        continue

                    query_lower = self.query.lower().strip()
                    query_words = query_lower.split()
                    name_lower = self.name.lower()

                    if any(word in query_lower for word in self.call_words):
                        for word in self.call_words:
                            if f'{word} {name_lower}' in query_lower:
                                self.called = True
                                logging.info("call detected!")
                                _, query = query_lower.split(f'{word} {name_lower}', 1)
                                if query.strip() == "" or len(query.strip().split()) < 2:
                                    self.query = None
                                    self.play_audio("start.wav")
                                else:
                                    self.query = query.strip()
                                break

                    if self.called is not True:
                        if query_words[0] == name_lower and len(query_words) > 2:
                            self.called = True
                            logging.info("call detected!")
                            self.query = " ".join(query_words[1:])

                        elif query_words[-1] == name_lower and len(query_words) > 2:
                            self.called = True
                            logging.info("call detected!")
                            self.query = " ".join(query_words[:-1])

                time.sleep(0.1)
        except IOError as e:
            logging.error(f'IOError in audio stream: {e}')
        except Exception as e:
            logging.error(f'Unexpected error in audio stream: {e}')
        finally:
            stream.stop_stream()
            stream.close()
            self.audio.terminate()
            logging.info("Audio stream terminated.")

    def run(self):
        self.speech_thread = threading.Thread(target=self.recognize_speech, daemon=True)
        self.threads.append(self.speech_thread)
        self.speech_thread.start()

        try:
            while True:
                if self.called:
                    with self.lock:
                        if self.query:
                            logging.info("processing...")
                            self.play_audio("end.wav")
                            self.called = False
                            self.speak(self.res_handler.handle(self.query))
                        self.query = None
                time.sleep(0.1)

        except KeyboardInterrupt:
            logging.info("Shutting down...")
            self.shutdown_flag.set()
            self.res_handler.save_cache()

            if self.threads:
                for thread in self.threads:
                    thread.join()
            logging.info("All threads terminated.")

if __name__ == '__main__':
    core = Core('Luna')
    core.run()
