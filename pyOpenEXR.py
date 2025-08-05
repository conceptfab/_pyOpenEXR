import os
import sys
import logging

# Konfiguracja logowania
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

import Imath
import numpy as np
import OpenEXR
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Importujemy kompletną klasę EXREditor z modułu core.ui.main_window
from core.ui.main_window import EXREditor

# Punkt wejścia aplikacji
if __name__ == "__main__":
    print("[INFO] Uruchamianie aplikacji EXR Editor", file=sys.stderr)
    app = QApplication(sys.argv)
    editor = EXREditor()
    editor.show()
    print("[INFO] Aplikacja została uruchomiona pomyślnie", file=sys.stderr)
    sys.exit(app.exec())