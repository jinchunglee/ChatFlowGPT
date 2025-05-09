class BaseAdapter:
    def format(self, context):
        raise NotImplementedError

    def call(self, formatted_input):
        raise NotImplementedError
