import requests
from .base_adapter import BaseAdapter

class LLaMA3_2Adapter(BaseAdapter):
    def __init__(self):
        self.model = "llama3.2"  # 根據你在 Ollama 裡的模型名稱來填

    def format(self, context):
        return {
            "model": self.model,
            "messages": context,
            "stream": False
        }

    def call(self, formatted_input):
        response = requests.post(
            "http://localhost:11434/api/chat",
            json=formatted_input
        )
        data = response.json()

        if "message" not in data or "content" not in data["message"]:
            raise RuntimeError(f"Ollama 回傳錯誤：{data}")
        
        return data["message"]["content"]
