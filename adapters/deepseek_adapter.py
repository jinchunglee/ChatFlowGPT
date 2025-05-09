import requests
from .base_adapter import BaseAdapter
import re

class DeepseekAdapter(BaseAdapter):
    def __init__(self):
        self.model = "deepseek-r1:7b"  # 你可改這名字對應你 Ollama 裡的 ID

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

        content = data["message"]["content"]
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content
