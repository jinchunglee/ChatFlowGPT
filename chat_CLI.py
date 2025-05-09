from dispatcher import ModelDispatcher
from memory import SharedMemory

def main():
    print("🔮 歡迎使用多模型對話器！輸入 `/switch` 切換模型，`/reset` 重設記憶，`/exit` 離開，`/?` 查看指令。")

    memory = SharedMemory()
    dispatcher = ModelDispatcher()

    while True:
        model_name = dispatcher.current_model
        prompt = input(f"[{model_name}] > ").strip()

        if prompt == "/exit":
            break
        elif prompt == "/switch":
            print(f"可用模型：{dispatcher.list_models()}")
            new_model = input("請輸入模型名稱：").strip()
            if dispatcher.switch_model(new_model):
                print(f"✅ 模型切換為 {new_model}")
            else:
                print("❌ 模型名稱錯誤")
            continue
        elif prompt == "/reset":
            memory.reset()
            print("🧼 已清除上下文")
            continue
        elif prompt == "/?":
            print("\n📘 指令列表：")
            print("  /switch  切換模型")
            print("  /reset   清除上下文記憶")
            print("  /exit    離開程式")
            print("  /?       顯示這份說明\n")
            continue

        memory.add_user_input(prompt)

        try:
            adapter = dispatcher.get_current_model()
            formatted = adapter.format(memory.get_context())
            response = adapter.call(formatted)
        except Exception as e:
            print(f"🔥 模型呼叫錯誤：{e}")
            continue

        memory.add_model_output(response)
        print(f"[{model_name}] 回答：{response}")

if __name__ == "__main__":
    main()