import sys
import logging
from PyQt6.QtWidgets import QApplication
from core.main_window import EXREditor

if __name__ == "__main__":
    # Konfiguracja logowania
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("[INFO] Uruchamianie aplikacji EXR Editor", file=sys.stderr)
    app = QApplication(sys.argv)
    editor = EXREditor()
    editor.show()
    print("[INFO] Aplikacja została uruchomiona pomyślnie", file=sys.stderr)
    sys.exit(app.exec())
