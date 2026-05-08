import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from frontend.main_window import FridayWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("FRIDAY")
    app.setWindowIcon(None)

    window = FridayWindow()
    window.show()

    sys.exit(app.exec())
