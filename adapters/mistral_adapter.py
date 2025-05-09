import requests
from .base_adapter import BaseAdapter

class MistralAdapter(BaseAdapter):
    def format(self, context):
        return {
            "model": "mistral",
            "messages": context,
            "stream": False
        }

    def call(self, formatted_input):
        try:
            resp = requests.post("http://localhost:11434/api/chat", json=formatted_input)
            return resp.json()["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollama 呼叫失敗：{str(e)}")
