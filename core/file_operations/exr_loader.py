"""
Moduł zawierający wątek do asynchronicznych operacji na plikach EXR.
"""

import sys
import logging
from PyQt6.QtCore import QThread, pyqtSignal

from .exr_reader import EXRReader
from .exr_writer import EXRWriter

logger = logging.getLogger(__name__)


class FileOperationThread(QThread):
    """
    Wątek do obsługi operacji plikowych (odczyt/zapis) w tle,
    aby interfejs użytkownika pozostał responsywny.
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, filepath, operation="load", data_to_save=None):
        super().__init__()
        self.filepath = filepath
        self.operation = operation
        self.data_to_save = data_to_save
        print(f"[INFO] Inicjalizacja wątku operacji plikowej: {operation} - {filepath}", file=sys.stderr)

    def run(self):
        try:
            print(f"[INFO] Rozpoczęcie operacji: {self.operation}", file=sys.stderr)
            if self.operation == "load":
                data = self._load_exr()
                print("[INFO] Plik został pomyślnie załadowany", file=sys.stderr)
                self.finished.emit(data)
            elif self.operation == "save" and self.data_to_save:
                self._save_exr()
                print("[INFO] Plik został pomyślnie zapisany", file=sys.stderr)
                self.finished.emit(None)  # Sygnalizuje zakończenie zapisu
        except Exception as e:
            print(f"[ERROR] Błąd podczas operacji na pliku: {e}", file=sys.stderr)
            self.error.emit(f"Wystąpił błąd podczas operacji na pliku:\n{e}")

    def _load_exr(self):
        """Wczytuje dane z pliku EXR."""
        return EXRReader.read_exr_file(self.filepath)

    def _save_exr(self):
        """Zapisuje dane do pliku EXR."""
        EXRWriter.save_exr_file(self.filepath, self.data_to_save) 