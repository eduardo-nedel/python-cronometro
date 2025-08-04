import sys
import time
import json
import os
import threading
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QDialog, QDialogButtonBox, QLineEdit, QFormLayout, QMessageBox
)

try:
    import keyboard  # type: ignore
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

CONFIG_FILE = "config.json"
DEFAULT_SHORTCUT = "]"

class KeyConfigDialog(QDialog):
    """
    Dialog para configurar o atalho de registro de tempo.
    """
    def __init__(self, register_seq, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Atalho")
        self.setModal(True)
        self.register_seq = register_seq

        self.register_input = QLineEdit(self.register_seq.toString())

        form = QFormLayout()
        form.addRow("Atalho para Registrar Tempo:", self.register_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def get_sequence(self):
        return QKeySequence(self.register_input.text())

class Stopwatch(QWidget):
    """
    Cronômetro: só existe iniciar (começa a contar) e finalizar (registra, zera e aguarda novo início).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cornometro v2 - Registrar Tempo")
        self.setMinimumSize(420, 350)
        self.setStyleSheet(self.dark_stylesheet())

        # Carrega o atalho salvo ou usa padrão
        self.register_seq = self.load_shortcut()

        # Estado do cronômetro
        self.running = False  # Começa parado
        self.start_time = 0.0
        self.elapsed = 0.0
        self.history = []
        self.compact_mode = False
        self.global_hotkey_registered = False

        # Elementos de UI
        self.time_label = QLabel("00:00:00.000")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Indicador de gravação para modo compacto (deve ser criado antes de set_time_label_style)
        self.compact_rec_indicator = QLabel(self)
        self.compact_rec_indicator.setFixedSize(14, 14)
        self.compact_rec_indicator.setStyleSheet(
            "background: #FF3333; border-radius: 7px; border: 1px solid #900;"
        )
        self.compact_rec_indicator.move(8, 8)
        self.compact_rec_indicator.setVisible(False)

        self.set_time_label_style(running=False)

        self.status_label = QLabel("Pronto")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.status_label.setStyleSheet("font-size: 18px; color: #AAA;")

        self.register_btn = QPushButton("Iniciar")
        self.register_btn.setStyleSheet(self.button_style())
        self.register_btn.clicked.connect(self.toggle)

        self.config_btn = QPushButton("Configurar Atalho")
        self.config_btn.setStyleSheet(self.button_style())
        self.config_btn.clicked.connect(self.configure_key)

        self.compact_mode_btn = QPushButton("Modo Compacto")
        self.compact_mode_btn.setStyleSheet(self.button_style())
        self.compact_mode_btn.clicked.connect(self.toggle_compact_mode)

        self.restore_btn = QPushButton("⤢")
        self.restore_btn.setFixedSize(28, 28)
        self.restore_btn.setStyleSheet("font-size: 18px; background: #222; color: #00FFAA; border: none; border-radius: 6px;")
        self.restore_btn.setToolTip("Restaurar modo completo")
        self.restore_btn.clicked.connect(self.toggle_compact_mode)
        self.restore_btn.setVisible(False)

        self.history_label = QLabel("Histórico de Registros:")
        self.history_list = QListWidget()
        self.history_list.setStyleSheet("background: #181818; color: #FFF; font-size: 16px; border-radius: 8px;")

        # Layouts
        self.top_layout = QHBoxLayout()
        self.top_layout.addStretch(1)
        self.top_layout.addWidget(self.time_label)
        self.top_layout.addStretch(1)

        self.status_layout = QHBoxLayout()
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addStretch(1)

        self.btn_layout = QHBoxLayout()
        self.btn_layout.addWidget(self.register_btn)
        self.btn_layout.addWidget(self.config_btn)
        self.btn_layout.addWidget(self.compact_mode_btn)

        self.main_layout = QVBoxLayout()
        # Botão de restaurar no canto superior direito
        self.restore_btn_layout = QHBoxLayout()
        self.restore_btn_layout.addStretch(1)
        self.restore_btn_layout.addWidget(self.restore_btn)
        self.main_layout.addLayout(self.restore_btn_layout)
        self.main_layout.addLayout(self.top_layout)
        self.main_layout.addLayout(self.status_layout)
        self.main_layout.addLayout(self.btn_layout)
        self.main_layout.addWidget(self.history_label)
        self.main_layout.addWidget(self.history_list)
        self.setLayout(self.main_layout)

        # Timer para atualização do display
        self.timer = QTimer(self)
        self.timer.setInterval(10)  # 10 ms para precisão de milissegundos
        self.timer.timeout.connect(self.update_time)
        self.timer.start()

        # Atalho global para registrar tempo
        self.shortcut_action = None
        self.register_shortcut()
        self.register_global_hotkey()

        # Indicador pisca ao finalizar
        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(180)  # ms
        self.blink_timer.setSingleShot(True)
        self.blink_timer.timeout.connect(self.show_time_label_normal)

    def dark_stylesheet(self):
        return """
        QWidget {
            background: #111;
            color: #EEE;
        }
        QLabel {
            background: transparent;
        }
        QListWidget {
            background: #181818;
            color: #FFF;
        }
        """

    def button_style(self):
        return """
        QPushButton {
            background: #222;
            color: #00FFAA;
            border: 2px solid #00FFAA;
            border-radius: 8px;
            font-size: 18px;
            padding: 10px 18px;
        }
        QPushButton:hover {
            background: #333;
            color: #FFF;
            border: 2px solid #FFF;
        }
        """

    def set_time_label_style(self, running):
        if self.compact_mode:
            self.time_label.setStyleSheet(
                "font-size: 36px; font-weight: bold; color: #00FFAA; background: transparent; border: none; padding: 0; margin: 0;"
            )
            # Indicador de gravação no modo compacto
            self.compact_rec_indicator.setVisible(running)
        else:
            self.compact_rec_indicator.setVisible(False)
            if running:
                self.time_label.setStyleSheet(
                    "font-size: 48px; font-weight: bold; color: #00FFAA; background: #222; border: 4px solid #FF3333; border-radius: 14px; padding: 20px;"
                )
            else:
                self.time_label.setStyleSheet(
                    "font-size: 48px; font-weight: bold; color: #00FFAA; background: #222; border: 4px solid #222; border-radius: 14px; padding: 20px;"
                )

    def register_shortcut(self):
        # Remove ação anterior se existir
        if self.shortcut_action:
            self.removeAction(self.shortcut_action)
        act = QAction(self)
        act.setShortcut(self.register_seq)
        act.triggered.connect(self.toggle)
        self.addAction(act)
        self.shortcut_action = act

    def register_global_hotkey(self):
        if not KEYBOARD_AVAILABLE:
            return
        # Remove hotkey anterior
        if self.global_hotkey_registered:
            import keyboard
            keyboard.remove_hotkey(self.global_hotkey_registered)
            self.global_hotkey_registered = False
        # Registra novo hotkey
        seq = self.register_seq.toString().replace("+", " ").lower()
        if seq:
            import keyboard
            self.global_hotkey_registered = keyboard.add_hotkey(seq, self.toggle_from_thread)

    def toggle_from_thread(self):
        # Só chama toggle se a janela NÃO estiver em foco
        if not self.isActiveWindow():
            QApplication.postEvent(self, _CustomEvent(self.toggle))

    def customEvent(self, event):
        if hasattr(event, 'callback'):
            event.callback()

    def toggle(self):
        if not self.running:
            # Inicia contagem
            self.running = True
            self.start_time = time.perf_counter()
            self.status_label.setText("Gravando...")
            self.status_label.setStyleSheet("font-size: 18px; color: #FF3333;")
            self.register_btn.setText("Finalizar")
            self.set_time_label_style(running=True)
        else:
            # Finaliza, registra, zera e para
            self.running = False
            self.elapsed = time.perf_counter() - self.start_time
            formatted = self.format_time(self.elapsed)
            self.history.append(formatted)
            self.history_list.addItem(formatted)
            self.history_list.scrollToBottom()
            self.status_label.setText(f"Registrado: {formatted}")
            self.status_label.setStyleSheet("font-size: 18px; color: #00FFAA;")
            self.register_btn.setText("Iniciar")
            self.visual_feedback(self.register_btn)
            self.set_time_label_style(running=False)
            self.blink_timer.start()
            # Zera o tempo
            self.start_time = 0.0
            self.elapsed = 0.0
            self.update_time()

    def toggle_compact_mode(self):
        self.compact_mode = not self.compact_mode
        for w in [self.status_label, self.config_btn, self.history_label, self.history_list, self.compact_mode_btn, self.register_btn]:
            w.setVisible(not self.compact_mode)
        self.time_label.setVisible(True)
        self.restore_btn.setVisible(self.compact_mode)
        if self.compact_mode:
            self.setFixedSize(260, 90)
            self.set_time_label_style(self.running)
            self.time_label.setMinimumSize(0, 0)
            self.time_label.setMaximumSize(16777215, 16777215)
            self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.restore_btn.setFixedSize(18, 18)
            self.restore_btn.setStyleSheet(
                "font-size: 13px; background: rgba(30,30,30,0.7); color: #EEE; border: none; border-radius: 4px;"
            )
            self.restore_btn.raise_()
            self.restore_btn.move(self.width() - self.restore_btn.width() - 4, 4)
            self.compact_rec_indicator.raise_()
            self.compact_rec_indicator.move(8, 8)
            self.top_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
        else:
            self.setMinimumSize(420, 350)
            self.setMaximumSize(16777215, 16777215)
            self.restore_btn.setVisible(False)
            self.set_time_label_style(self.running)
            self.time_label.setMinimumSize(0, 0)
            self.time_label.setMaximumSize(16777215, 16777215)
            self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.restore_btn.setFixedSize(28, 28)
            self.restore_btn.setStyleSheet(
                "font-size: 18px; background: #222; color: #00FFAA; border: none; border-radius: 6px;"
            )
            self.top_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setContentsMargins(9, 9, 9, 9)
            self.resize(600, 400)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Garante que o botão de restaurar fique no canto superior direito no modo compacto
        if self.compact_mode and self.restore_btn.isVisible():
            self.restore_btn.move(self.width() - self.restore_btn.width() - 8, 8)

    def update_time(self):
        # Atualiza o display do tempo
        if self.running:
            self.elapsed = time.perf_counter() - self.start_time
        self.time_label.setText(self.format_time(self.elapsed))

    @staticmethod
    def format_time(seconds):
        ms = int((seconds - int(seconds)) * 1000)
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"

    def configure_key(self):
        # Dialog para configurar o atalho
        dlg = KeyConfigDialog(self.register_seq, self)
        if dlg.exec():
            new_seq = dlg.get_sequence()
            if not new_seq.toString():
                QMessageBox.warning(self, "Atalho Inválido", "O atalho não pode ser vazio.")
                return
            self.register_seq = new_seq
            self.save_shortcut(new_seq)
            self.register_shortcut()
            self.register_global_hotkey()
            QMessageBox.information(self, "Atalho Atualizado", f"Novo atalho: {self.register_seq.toString()}")

    def visual_feedback(self, widget):
        # Feedback visual rápido no botão
        orig_style = widget.styleSheet()
        widget.setStyleSheet(orig_style + "background: #00FFAA; color: #111;")
        QTimer.singleShot(120, lambda: widget.setStyleSheet(orig_style))

    def show_time_label_normal(self):
        self.set_time_label_style(running=self.running)

    def load_shortcut(self):
        # Carrega o atalho salvo em arquivo
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    seq = data.get("register_shortcut", DEFAULT_SHORTCUT)
                    return QKeySequence(seq)
            except Exception:
                pass
        return QKeySequence(DEFAULT_SHORTCUT)

    def save_shortcut(self, seq):
        # Salva o atalho em arquivo
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"register_shortcut": seq.toString()}, f)
        except Exception:
            pass

# Evento customizado para chamada cross-thread
from PyQt6.QtCore import QEvent
class _CustomEvent(QEvent):
    def __init__(self, callback):
        super().__init__(QEvent.Type(QEvent.registerEventType()))
        self.callback = callback

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = Stopwatch()
    win.show()
    sys.exit(app.exec())
