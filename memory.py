class SharedMemory:
    def __init__(self):
        self.history = []

    def add_user_input(self, text):
        self.history.append({"role": "user", "content": text})

    def add_model_output(self, text):
        self.history.append({"role": "assistant", "content": text})

    def get_context(self):
        return self.history[-20:]  # 最多保留 20 組對話

    def reset(self):
        self.history = []
