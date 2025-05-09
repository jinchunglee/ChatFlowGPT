from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTextEdit,
    QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QLineEdit, QSizePolicy, QProgressBar,
    QSplitter, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsLineItem, QGraphicsItemGroup,QGraphicsProxyWidget
)
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPen, QPainter, QWheelEvent, QTextDocument, QFont
from dispatcher import ModelDispatcher
from memory import SharedMemory
from functools import partial
import sys
import uuid

class CustomGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.zoom_factor = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 2.0

    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom = zoom_in_factor
        else:
            zoom = zoom_out_factor

        new_zoom = self.zoom_factor * zoom
        if self.min_zoom <= new_zoom <= self.max_zoom:
            self.zoom_factor = new_zoom
            self.scale(zoom, zoom)

class FlowScene(QGraphicsScene):
    def __init__(self, parent=None, click_callback=None):
        super().__init__(parent)
        self.node_width = 180
        self.node_height = 70
        self.spacing_y = 100
        self.spacing_x = 240
        self.nodes = []  # 存儲節點 (group, x, y, level, branch_index, node_id)
        self.lines = []  # 存儲線條
        self.click_callback = click_callback
        self.branch_indices = {}  # {level: max_branch_index}

 

    def add_node(self, text, level, is_user, highlight=False, branch_index=0, node_id=None):
        if not is_user:
            return

        x = self.spacing_x * branch_index
        y = level * self.spacing_y
        max_w = self.node_width - 20          # 文字可用寬度（留 padding）

        # ---- 建立文字項目，設定自動換行寬度 ----
        label = QGraphicsTextItem(text)
        label.setTextWidth(max_w)
        font = label.font()
        font.setPointSize(11)
        font.setBold(True)
        label.setFont(font)
        label.setDefaultTextColor(Qt.white)

        # 量測真實高度（含內文）
        txt_h = label.boundingRect().height()
        total_h = txt_h + 20                  # + 上下 padding

        # ---- 背景矩形 ----
        rect = QGraphicsRectItem(0, 0, self.node_width, total_h)
        rect.setBrush(Qt.green if highlight else Qt.darkCyan)
        rect.setPen(QPen(Qt.white, 2))
        rect.setPos(x, y)

        # 文字擺進來（+10,+10 padding）
        label.setPos(x + 10, y + 10)

        # ---- 群組成一個節點 ----
        group = QGraphicsItemGroup()
        group.addToGroup(rect)
        group.addToGroup(label)
        group.setData(0, level)
        group.setData(1, branch_index)
        group.setData(2, node_id)
        group.setToolTip(text)
        group.setFlag(QGraphicsItemGroup.ItemIsSelectable, True)

        def handler(event, lvl=level, br_idx=branch_index, nid=node_id):
            if self.click_callback:
                self.click_callback(lvl, br_idx, nid)
        group.mousePressEvent = partial(handler)

        self.addItem(group)
        self.nodes.append((group, x, y, level, branch_index, node_id))

        self.redraw_lines()






    def redraw_lines(self):
        # 清除現有線條
        for line in self.lines:
            self.removeItem(line)
        self.lines = []

        node_map = {(n[3], n[4]): n for n in self.nodes if n[5]}  # {(level, branch_index): node}

        for node in self.nodes:
            group, x, y, level, branch_index, node_id = node
            if level == 0 or not node_id:
                continue

            parent_level = level - 1
            # 嘗試找與該 branch_index 對應的父節點
            same_branch_parent = node_map.get((parent_level, branch_index))
            any_parent = None

            if same_branch_parent:
                any_parent = same_branch_parent
            else:
                # 若非同 branch，則嘗試找出上一層任何父節點
                possible_parents = [n for n in self.nodes if n[3] == parent_level]
                if possible_parents:
                    # 找最接近 y 軸的那個
                    possible_parents.sort(key=lambda n: abs(n[1] - x))
                    any_parent = possible_parents[0]

            if any_parent:
                parent_x, parent_y = any_parent[1], any_parent[2]
                parent_center_x = parent_x + self.node_width / 2
                parent_center_y = parent_y + self.node_height
                node_center_x = x + self.node_width / 2
                node_center_y = y

                line = QGraphicsLineItem(
                    parent_center_x, parent_center_y,
                    node_center_x, node_center_y
                )
                pen = QPen(Qt.white)
                pen.setWidth(2)  # 線條加粗
                pen.setCosmetic(True)  # 不跟 zoom 比例變化
                line.setPen(pen)

                self.addItem(line)         # ✅ 加回這行，才能讓線條顯示
                self.lines.append(line)



    def clear(self):
        super().clear()
        self.nodes = []
        self.lines = []
        self.branch_indices = {}

    def has_child(self, level, branch_index, history):
        for item in history:
            if item.get('is_user', True) and item['level'] == level + 1 and item['branch_index'] == branch_index:
                return True
        return False

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧠 多模型本地對話器 (Ollama-powered)")
        self.setMinimumSize(1080, 640)

        self.dispatcher = ModelDispatcher()
        self.memory = SharedMemory()
        self.dark_mode = True
        self.lang_is_en = False

        self.flow_level = 0
        self.current_branch_index = 0
        self.current_node_id = None
        self.branch_history = {}  # { (level, branch_index): [node_ids] }

        self._init_ui()
        self.set_dark_theme()

    def _init_ui(self):
        splitter = QSplitter()
        left_panel = QWidget()
        left_layout = QVBoxLayout()

        self.graphics_view = CustomGraphicsView()
        self.scene = FlowScene(click_callback=self.restore_to_level)
        self.graphics_view.setScene(self.scene)

        self.flow_label = QLabel("🧭 對話流程圖")  # 語言可切換
        left_layout.addWidget(self.flow_label)
        left_layout.addWidget(self.graphics_view)
        left_panel.setLayout(left_layout)

        right_panel = QWidget()
        right_layout = QVBoxLayout()

        control_layout = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.dispatcher.list_models())
        self.model_combo.currentTextChanged.connect(self.switch_model_from_combo)


        self.model_label = QLabel("模型選擇：")  # 語言可切換
        # self.switch_btn = QPushButton("切換模型")
        # self.switch_btn.clicked.connect(self.switch_model)

        self.reset_btn = QPushButton("🧼 清除對話")
        self.reset_btn.clicked.connect(self.clear_context)

        self.theme_btn = QPushButton("🌙 切換主題")
        self.theme_btn.clicked.connect(self.toggle_theme)

        self.lang_btn = QPushButton("🌐 English")
        self.lang_btn.clicked.connect(self.toggle_language)

        control_layout.addWidget(self.model_label)
        control_layout.addWidget(self.model_combo)
        #control_layout.addWidget(self.switch_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.theme_btn)
        control_layout.addWidget(self.reset_btn)
        control_layout.addWidget(self.lang_btn)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("font-size: 14px;")

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("請輸入訊息...")
        self.input_field.returnPressed.connect(self.send_message)

        self.send_btn = QPushButton("送出")
        self.send_btn.clicked.connect(self.send_message)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setVisible(False)
        self.loading_bar.setTextVisible(False)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)

        right_layout.addLayout(control_layout)
        right_layout.addWidget(self.chat_display, 1)
        right_layout.addLayout(input_layout)
        right_layout.addWidget(self.loading_bar)
        right_panel.setLayout(right_layout)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])

        self.setCentralWidget(splitter)



        

    def switch_model_from_combo(self, selected_model):
        self.dispatcher.switch_model(selected_model)
        if self.lang_is_en:
            self.append_to_display(f"[System] ✅ Switched to model: {selected_model}")
        else:
            self.append_to_display(f"[系統] ✅ 已切換為模型：{selected_model}")


    def clear_context(self):
        self.memory.reset()
        self.chat_display.clear()
        self.scene.clear()
        self.flow_level = 0
        self.current_branch_index = 0
        self.current_node_id = None
        self.branch_history = {}
        self.append_to_display("[系統] ✅ 對話已清除\n")

    def append_to_display(self, text, is_user=False, override_align=None):
        color = "#444" if not is_user else "#333"
        align = override_align if override_align else ("right" if is_user else "left")
        html = f'<div align="{align}"><div style="background-color:{color};padding:6px 10px;margin:4px 0;border-radius:10px;display:inline-block;color:white;max-width:70%;">{text}</div></div>'
        self.chat_display.append(html)

    def send_message(self):
        user_input = self.input_field.text().strip()
        if not user_input:
            return

        self.append_to_display(user_input, is_user=True)
        new_node_id = str(uuid.uuid4())

        # 根據 current_node_id 找 parent node
        parent_node = next((item for item in self.memory.history
                            if item.get('is_user', True) and item.get('node_id') == self.current_node_id), None)

        if parent_node:
            parent_level = parent_node['level']
            parent_branch_index = parent_node['branch_index']

            # 找所有來自同一 parent 的子節點
            same_parent_children = [
                item for item in self.memory.history
                if item.get('is_user', True) and item.get('parent_node_id') == parent_node['node_id']
            ]

            if same_parent_children:
                existing_indices = {item['branch_index'] for item in same_parent_children}
                new_branch_index = max(existing_indices, default=parent_branch_index) + 1
            else:
                new_branch_index = parent_branch_index

            new_level = parent_level + 1
        else:
            # fallback：首次訊息或資料遺失
            new_level = self.flow_level
            new_branch_index = self.current_branch_index

        # 更新狀態指標
        self.flow_level = new_level
        self.current_branch_index = new_branch_index
        self.current_node_id = new_node_id

        # 加入 memory 並補足 metadata
        self.memory.add_user_input(user_input)
        self.memory.history[-1]['level'] = new_level
        self.memory.history[-1]['branch_index'] = new_branch_index
        self.memory.history[-1]['node_id'] = new_node_id
        self.memory.history[-1]['parent_node_id'] = parent_node['node_id'] if parent_node else None

        # 加入 branch 歷史
        key = (new_level, new_branch_index)
        if key not in self.branch_history:
            self.branch_history[key] = []
        self.branch_history[key].append(new_node_id)

        # 重畫流程圖
        self.redraw_flowchart()

        self.loading_bar.setVisible(True)
        self.input_field.clear()
        QTimer.singleShot(100, self.run_model_response)



    def run_model_response(self):
        try:
            adapter = self.dispatcher.get_current_model()
            formatted = adapter.format(self.memory.get_context())
            response = adapter.call(formatted)
        except Exception as e:
            response = f"[錯誤] 模型呼叫失敗：{e}"

        self.memory.add_model_output(response)
        self.memory.history[-1]['level'] = self.flow_level
        self.memory.history[-1]['branch_index'] = self.current_branch_index
        self.append_to_display(response, is_user=False)

        self.flow_level += 1
        self.scene.clear()
        for item in self.memory.history:
            if item.get('is_user', True):
                if 'node_id' not in item:
                    print(f"Warning: User input missing node_id: content={item['content'][:10]}")
                    continue
                print(f"Adding node: content={item['content'][:10]}, level={item['level']}, branch={item['branch_index']}, node_id={item['node_id']}")
                display_text = item['content']  
                self.scene.add_node(
                    display_text,
                    item['level'],
                    is_user=True,
                    highlight=(item['node_id'] == self.current_node_id),
                    branch_index=item['branch_index'],
                    node_id=item['node_id']
                )
        self.loading_bar.setVisible(False)




    def redraw_flowchart(self):
        self.chat_display.clear()
        self.scene.clear()

        current_level = -1
        current_branch = -1
        for item in self.memory.history:
            if item.get('is_user', True) and item.get('node_id') == self.current_node_id:
                current_level = item['level']
                current_branch = item['branch_index']
                break

        for item in self.memory.history:
            if item.get('is_user', True):
                if 'node_id' not in item:
                    print(f"Warning: User input missing node_id: content={item['content'][:10]}")
                    continue
                print(f"Adding node: content={item['content'][:10]}, level={item['level']}, branch={item['branch_index']}, node_id={item['node_id']}")
                display_text = item['content']  
                self.scene.add_node(
                    display_text,
                    item['level'],
                    is_user=True,
                    highlight=(item['node_id'] == self.current_node_id),
                    branch_index=item['branch_index'],
                    node_id=item['node_id']
                )

        for idx, item in enumerate(self.memory.history):
            if item.get('is_user', True):
                if (item['level'] <= current_level and (item['branch_index'] == current_branch or item['level'] < current_level)):
                    self.append_to_display(item['content'], is_user=True, override_align="left")
            elif not item.get('is_user', True):
                for user_item in self.memory.history:
                    if user_item.get('is_user', True) and user_item.get('node_id', '') == item.get('node_id', '') and \
                       user_item['level'] <= current_level and (user_item['branch_index'] == current_branch or user_item['level'] < current_level):
                        self.append_to_display(item['content'], is_user=False)
                        break

        print("Memory history:", self.memory.history)


    def restore_to_level(self, level, branch_index, node_id):
        print(f"Restoring to level {level}, branch {branch_index}, node_id {node_id}")
        self.branch_point = level
        self.current_branch_index = branch_index
        self.current_node_id = node_id
        self.flow_level = level + 1
        self.redraw_flowchart()

    def toggle_theme(self):
        if self.dark_mode:
            self.set_light_theme()
        else:
            self.set_dark_theme()
        self.dark_mode = not self.dark_mode

    def set_dark_theme(self):
        self.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            color: #dddddd;
        }
        QPushButton, QLineEdit, QComboBox, QTextEdit {
            background-color: #3c3f41;
            color: #ffffff;
            border: 1px solid #555555;
        }
        QPushButton:hover {
            background-color: #505357;
        }
        QGraphicsView {
            background-color: #2b2b2b;
        }
        """)

    def set_light_theme(self):
        self.setStyleSheet("""
        QWidget {
            background-color: #f0f0f0;
            color: #333333;
        }
        QPushButton, QLineEdit, QComboBox, QTextEdit {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cccccc;
        }
        QPushButton:hover {
            background-color: #dddddd;
        }
        QGraphicsView {
            background-color: #ffffff;
        }
        """)

    def toggle_language(self):
        self.lang_is_en = not self.lang_is_en
        if self.lang_is_en:
            self.lang_btn.setText("🌐 中文")
            self.reset_btn.setText("🧼 Clear Context")
            self.theme_btn.setText("🌙 Theme")
            self.send_btn.setText("Send")  # ✅ NEW
            self.model_label.setText("Model:")  # ✅ NEW
            self.flow_label.setText("🧭 Flowchart")  # ✅ NEW
            self.model_combo.setToolTip("Select a model")
            self.input_field.setPlaceholderText("Type your message...")
            self.setWindowTitle("🧠 Multi-Model Local Chat (Ollama-powered)")
        else:
            self.lang_btn.setText("🌐 English")
            self.reset_btn.setText("🧼 清除對話")
            self.theme_btn.setText("🌙 切換主題")
            self.send_btn.setText("送出")  # ✅ NEW
            self.model_label.setText("模型選擇：")  # ✅ NEW
            self.flow_label.setText("🧭 對話流程圖")  # ✅ NEW
            self.model_combo.setToolTip("選擇模型")
            self.input_field.setPlaceholderText("請輸入訊息...")
            self.setWindowTitle("🧠 多模型本地對話器 (Ollama-powered)")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())