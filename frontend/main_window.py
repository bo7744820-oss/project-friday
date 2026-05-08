import math
import sys
import threading
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QKeySequence, QPainter, QColor, QPen, QRadialGradient, QPointF
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QShortcut,
)

from backend.friday_core import FridayCore


class OrbWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.0
        self.pulse = 0.0
        self.active = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.timer.start(40)
        self.setMinimumSize(320, 320)

    def advance(self):
        self.phase += 0.22
        self.pulse = (self.pulse + 0.08) % 2.0
        self.update()

    def set_active(self, active: bool):
        self.active = active

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()
        radius = min(self.width(), self.height()) // 2 - 12

        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0.0, QColor(77, 204, 255, 220))
        gradient.setColorAt(0.6, QColor(7, 29, 57, 180))
        gradient.setColorAt(1.0, QColor(4, 11, 30, 220))
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius, radius)

        ring_pen = QPen(QColor(80, 180, 255, 140), 2)
        painter.setPen(ring_pen)
        painter.drawEllipse(center, int(radius * 0.82), int(radius * 0.82))
        painter.drawEllipse(center, int(radius * 0.62), int(radius * 0.62))

        wave_count = 8
        for index in range(wave_count):
            angle = self.phase + index * (2 * math.pi / wave_count)
            offset = int(radius * 0.2 * (0.9 + 0.1 * self.pulse))
            x = center.x() + int(offset * math.cos(angle))
            y = center.y() + int(offset * math.sin(angle))
            alpha = 120 + int(120 * (index / wave_count))
            painter.setPen(QPen(QColor(78, 186, 255, alpha), 2))
            painter.drawLine(center, QPointF(x, y))

        if self.active:
            active_pen = QPen(QColor(140, 235, 255, 210), 4)
            painter.setPen(active_pen)
            painter.drawEllipse(center, int(radius * 0.4), int(radius * 0.4))

        painter.setPen(QPen(QColor(180, 232, 255, 220), 3))
        painter.drawEllipse(center, int(radius * 0.12), int(radius * 0.12))


class FridayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.core = FridayCore()
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self._append_typing)
        self.typing_buffer = ""
        self.typing_position = 0

        self.setWindowTitle("FRIDAY")
        self.setMinimumSize(1300, 820)

        self._load_style()
        self._build_ui()
        self._connect_signals()
        threading.Thread(target=self._refresh_external_data, daemon=True).start()

        self.core.startup_sequence()
        self.core.start_wake_word_detection()

    def _load_style(self):
        style_path = Path(__file__).resolve().parent.parent / "assets" / "style.qss"
        if style_path.exists():
            with open(style_path, "r", encoding="utf-8") as fh:
                self.setStyleSheet(fh.read())

    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(18)

        header = QHBoxLayout()
        title = QLabel("FRIDAY")
        title.setObjectName("titleLabel")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.status_text = QLabel("Initializing interface...")
        self.status_text.setObjectName("statusLabel")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status_text)
        root_layout.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(16)

        left_panel = self._create_info_panel()
        right_panel = self._create_chat_panel()

        center_panel = self._create_center_panel()

        content.addWidget(left_panel, 1)
        content.addWidget(center_panel, 1)
        content.addWidget(right_panel, 1)
        root_layout.addLayout(content)

        footer = self._create_footer()
        root_layout.addWidget(footer)

        self.setCentralWidget(root)
        self._register_shortcuts()

    def _create_info_panel(self):
        panel = QFrame()
        panel.setObjectName("glassPanel")
        panel.setMinimumWidth(280)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.stats_header = QLabel("SYSTEM DASHBOARD")
        self.stats_header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(self.stats_header)

        self.cpu_label = QLabel("CPU: -- %")
        self.ram_label = QLabel("RAM: -- %")
        self.battery_label = QLabel("BATTERY: -- %")
        self.network_label = QLabel("NETWORK: -- KB/s")
        self.weather_label = QLabel("Weather: unknown")
        self.news_label = QLabel("News: fetching...")

        for widget in [self.cpu_label, self.ram_label, self.battery_label, self.network_label, self.weather_label, self.news_label]:
            layout.addWidget(widget)

        layout.addStretch()
        return panel

    def _create_center_panel(self):
        panel = QFrame()
        panel.setObjectName("glassPanel")
        panel.setMinimumWidth(320)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.orb = OrbWidget()
        self.orb.setObjectName("orbFrame")
        layout.addWidget(self.orb, alignment=Qt.AlignmentFlag.AlignCenter)

        self.orb_status = QLabel("Orb status: waiting for wake word")
        self.orb_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.orb_status)

        self.startup_bar = QLabel("Starting up FRIDAY...")
        self.startup_bar.setStyleSheet("color: #7fb9ff;")
        layout.addWidget(self.startup_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        return panel

    def _create_chat_panel(self):
        panel = QFrame()
        panel.setObjectName("glassPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.chat_log = QTextEdit()
        self.chat_log.setObjectName("chatLog")
        self.chat_log.setReadOnly(True)
        self.chat_log.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.chat_log.setMinimumHeight(420)
        layout.addWidget(self.chat_log)

        self.response_label = QLabel("Ready for input.")
        self.response_label.setObjectName("responseLabel")
        layout.addWidget(self.response_label)

        controls = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Ask FRIDAY anything... (Ctrl+L to listen)")
        controls.addWidget(self.command_input)

        send_button = QPushButton("Send")
        send_button.clicked.connect(self._handle_send)
        controls.addWidget(send_button)

        listen_button = QPushButton("Listen")
        listen_button.clicked.connect(self.core.listen_once)
        controls.addWidget(listen_button)

        layout.addLayout(controls)
        return panel

    def _create_footer(self):
        panel = QFrame()
        panel.setObjectName("glassPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        self.quick_status = QLabel("Dark mode engaged. Neon core active.")
        layout.addWidget(self.quick_status)

        layout.addStretch()
        self.clear_button = QPushButton("Clear Chat")
        self.clear_button.clicked.connect(self._clear_chat)
        layout.addWidget(self.clear_button)

        return panel

    def _register_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.core.listen_once)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._handle_send)

    def _connect_signals(self):
        self.core.response_ready.connect(self._on_response)
        self.core.system_stats_updated.connect(self._update_system_stats)
        self.core.status_changed.connect(self._update_status)
        self.core.startup_progress.connect(self._on_startup_step)
        self.core.wake_word_detected.connect(self._on_wake_word)
        self.core.error_occurred.connect(self._on_error)
        self.core.speaking_started.connect(lambda: self.orb.set_active(True))
        self.core.speaking_finished.connect(lambda: self.orb.set_active(False))
        self.core.listening_started.connect(lambda: self.orb.set_active(True))
        self.core.listening_finished.connect(lambda: self.orb.set_active(False))

    def _on_startup_step(self, progress: int, message: str):
        self.startup_bar.setText(f"{progress}% — {message}")
        if progress == 100:
            self.startup_bar.setText("FRIDAY is online and ready.")

    def _on_wake_word(self):
        self.orb_status.setText("Wake word detected. Listening now.")
        self.status_text.setText("Wake word detected")

    def _on_error(self, error: str):
        self.response_label.setText(error)
        self.chat_log.append(f"<span style='color:#ff6b6b;'>ERROR:</span> {error}")

    def _on_response(self, message: str):
        self.response_label.setText("FRIDAY has responded.")
        self._begin_typing(message)

    def _begin_typing(self, message: str):
        self.typing_buffer = message
        self.typing_position = 0
        self.response_label.setText("FRIDAY is typing...")
        self.typing_timer.start(40)

    def _append_typing(self):
        self.typing_timer.stop()
        if self.typing_position < len(self.typing_buffer):
            self.typing_position += 3
            preview = self.typing_buffer[: self.typing_position]
            self.response_label.setText(f"{preview}▌")
            self.typing_timer.start(30)
        else:
            self.chat_log.append(f"<span style='color:#d6e9ff;'>FRIDAY: {self.typing_buffer}</span>")
            self.chat_log.append("<hr>")
            self.typing_buffer = ""
            self.response_label.setText("Ready for the next command.")

    def _handle_send(self):
        user_text = self.command_input.text().strip()
        if not user_text:
            return
        self.chat_log.append(f"<span style='color:#8dd0ff;'>You: {user_text}</span>")
        self.command_input.clear()
        self.core.process_command(user_text)

    def _update_system_stats(self, stats: dict):
        self.cpu_label.setText(f"CPU: {stats.get('cpu', 0):.1f}%")
        self.ram_label.setText(f"RAM: {stats.get('ram', 0):.1f}%")
        battery_text = f"{stats.get('battery', 0):.0f}%" if stats.get('battery', -1) >= 0 else "n/a"
        self.battery_label.setText(f"BATTERY: {battery_text}")
        net_sent = stats.get('net_sent', 0) / 1024
        net_recv = stats.get('net_recv', 0) / 1024
        self.network_label.setText(f"NETWORK: {net_sent:.1f} KB sent / {net_recv:.1f} KB recv")

    def _update_status(self, status: str):
        self.status_text.setText(status)

    def _clear_chat(self):
        self.chat_log.clear()
        self.response_label.setText("Conversation cleared.")

    def _refresh_external_data(self):
        weather = self.core.get_weather()
        if weather.get("error"):
            self.weather_label.setText("Weather unavailable.")
        else:
            self.weather_label.setText(
                f"Weather: {weather.get('temp', '--')}°C, {weather.get('description', 'Unknown')}"
            )

        news = self.core.get_news()
        if news:
            self.news_label.setText("News: " + " | ".join(item.get("title", "") for item in news[:3]))
        else:
            self.news_label.setText("News unavailable.")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = FridayWindow()
    window.show()
    sys.exit(app.exec())
