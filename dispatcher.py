#from adapters.gpt_adapter import GPTAdapter
from adapters.mistral_adapter import MistralAdapter
from adapters.deepseek_adapter import DeepseekAdapter
from adapters.llama3_2_adapter import LLaMA3_2Adapter

class ModelDispatcher:
    def __init__(self):
        self.models = {
            #"gpt": GPTAdapter(),
            "mistral-4b": MistralAdapter(),
            "deepseek-r1-7b": DeepseekAdapter(),
            "llama3.2-3b": LLaMA3_2Adapter(),
        }
        self.current_model = "deepseek-r1-7b"

    def switch_model(self, model_name):
        if model_name in self.models:
            self.current_model = model_name
            return True
        return False

    def get_current_model(self):
        return self.models[self.current_model]

    def list_models(self):
        return list(self.models.keys())


