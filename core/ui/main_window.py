"""
Główne okno aplikacji EXR Editor.
"""

import sys
import os
import logging
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QFileDialog, QApplication

from .components import (
    TreeNavigator, ImagePreview, ControlPanel, 
    MetadataPanel, TabManager, MenuManager
)
from ..file_operations import FileOperationThread
from ..data_processing import ImageProcessor, MetadataHandler

logger = logging.getLogger(__name__)


class EXREditor(QMainWindow):
    """
    Główne okno aplikacji EXR Editor.
    """
    
    def __init__(self):
        super().__init__()
        print("[INFO] Inicjalizacja aplikacji EXR Editor", file=sys.stderr)
        self.setWindowTitle("Przeglądarka i Edytor Plików OpenEXR")
        self.setGeometry(100, 100, 1600, 900)

        self.exr_data = None
        self.current_preview_data = None
        self.file_thread = None

        self._init_ui()
        self._create_menus()
        print("[INFO] Aplikacja została zainicjalizowana pomyślnie", file=sys.stderr)

    def _init_ui(self):
        """Inicjalizuje interfejs użytkownika."""
        # Główny widget i layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Splitter do zmiany rozmiarów paneli
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- Panel lewy: Nawigacja (Drzewo) ---
        self.tree_widget = TreeNavigator.create_tree_widget()
        self.tree_widget.currentItemChanged.connect(self.on_tree_item_selected)
        splitter.addWidget(self.tree_widget)

        # --- Panel centralny i prawy w jednym kontenerze ---
        right_container = QSplitter(Qt.Orientation.Vertical)

        # --- Panel centralny: Podgląd obrazu ---
        self.image_preview = ImagePreview.create_preview_widget()
        right_container.addWidget(self.image_preview)

        # --- Panel prawy: Edycja i metadane ---
        self.control_widget, self.brightness_slider, self.contrast_slider = ControlPanel.create_control_widget()
        self.brightness_slider.valueChanged.connect(self.update_display)
        self.contrast_slider.valueChanged.connect(self.update_display)

        self.metadata_table = MetadataPanel.create_metadata_widget()
        self.tabs = TabManager.create_tab_widget(self.control_widget, self.metadata_table)

        right_container.addWidget(self.tabs)
        splitter.addWidget(right_container)

        splitter.setSizes([300, 1300])
        right_container.setSizes([600, 300])

    def _create_menus(self):
        """Tworzy pasek menu."""
        MenuManager.create_menu_bar(
            self, 
            self.open_file_dialog, 
            self.save_file, 
            self.save_file_as
        )

    def open_file_dialog(self):
        print("[INFO] Otwieranie okna dialogowego wyboru pliku", file=sys.stderr)
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Otwórz plik OpenEXR", "", "OpenEXR Files (*.exr)"
        )
        if filepath:
            print(f"[INFO] Wybrano plik do załadowania: {filepath}", file=sys.stderr)
            self.image_preview.setText("Ładowanie pliku, proszę czekać...")
            QApplication.processEvents()  # Odśwież UI
            # --- ŁADOWANIE SYNCHRONICZNE ---
            try:
                from core.file_operations.exr_reader import EXRReader
                data = EXRReader.read_exr_file(filepath)
                self.on_file_loaded(data)
            except Exception as e:
                self.on_file_error(str(e))
        else:
            print("[INFO] Anulowano wybór pliku", file=sys.stderr)

    def on_file_loaded(self, loaded_data):
        """Obsługuje załadowanie pliku."""
        print("[INFO] Plik został załadowany pomyślnie", file=sys.stderr)
        # Normalizacja formatu danych z wątku (dict lub obiekt) do dict
        if isinstance(loaded_data, dict):
            normalized = loaded_data
        else:
            try:
                normalized = {
                    "filepath": getattr(loaded_data, "filepath", ""),
                    "parts": []
                }
                for p in getattr(loaded_data, "parts", []):
                    normalized["parts"].append({
                        "name": getattr(p, "name", "default"),
                        "header": getattr(p, "header", {}),
                        "size": getattr(p, "size", (0, 0)),
                        "channels": getattr(p, "channels", {}),
                        "layers": getattr(p, "layers", {})
                    })
            except Exception:
                normalized = {"filepath": "", "parts": []}
        self.exr_data = normalized

        path_for_title = self.exr_data.get("filepath", "")
        self.setWindowTitle(
            f"EXR Editor - {os.path.basename(path_for_title)}"
        )
        TreeNavigator.populate_tree(self.tree_widget, self.exr_data)
        self.image_preview.setText("Wybierz element z drzewa, aby wyświetlić podgląd.")
        print(f"[INFO] Zaktualizowano interfejs dla pliku: {self.exr_data.get('filepath', '')}", file=sys.stderr)

    def on_file_error(self, error_message):
        """Obsługuje błędy podczas operacji na plikach."""
        print(f"[ERROR] Błąd podczas operacji na pliku: {error_message}", file=sys.stderr)
        self.image_preview.setText("Nie udało się załadować pliku.")

    def on_tree_item_selected(self, current_item, previous_item):
        """Obsługuje wybór elementu w drzewie."""
        if not current_item or not self.exr_data:
            return

        item_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        item_type, part_idx, *rest = item_data
        parts_list = self.exr_data.get("parts", [])
        if not isinstance(part_idx, int) or part_idx < 0 or part_idx >= len(parts_list):
            return
        part_data = parts_list[part_idx]
        print(f"[INFO] Wybrano element: {item_type} w części {part_idx}", file=sys.stderr)

        header = part_data.get("header", {})
        MetadataHandler.populate_metadata_table(self.metadata_table, header)

        self.current_preview_data = None

        # Wybór danych do podglądu
        if item_type == "layer":
            layer_name = rest[0]
            self.current_preview_data = ImageProcessor.prepare_preview_data(
                part_data, "layer", layer_name=layer_name
            )
        elif item_type == "channel":
            ch_name = str(rest[0])
            self.current_preview_data = ImageProcessor.prepare_preview_data(
                part_data, "channel", channel_name=ch_name
            )

        # Zresetuj suwaki i odśwież podgląd
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(100)
        self.update_display()

    def update_display(self):
        """Aktualizuje wyświetlanie obrazu."""
        if self.current_preview_data is None:
            self.image_preview.clear()
            return

        # Pobierz wartości z suwaków
        brightness = self.brightness_slider.value() / 100.0
        contrast = self.contrast_slider.value() / 100.0

        # Zastosuj korekty i konwertuj na obraz
        adjusted_data = ImageProcessor.apply_display_adjustments(
            self.current_preview_data, brightness, contrast
        )
        q_image = ImageProcessor.numpy_to_qimage(adjusted_data)
        pixmap = ImageProcessor.create_scaled_pixmap(q_image, self.image_preview.size())
        
        if pixmap:
            self.image_preview.setPixmap(pixmap)

    def save_file(self):
        """Zapisuje plik."""
        if self.exr_data and self.exr_data.get("filepath"):
            print(f"[INFO] Zapisywanie pliku: {self.exr_data['filepath']}", file=sys.stderr)
            self._execute_save(self.exr_data["filepath"])
        else:
            print("[INFO] Brak ścieżki pliku, otwieranie okna 'Zapisz jako'", file=sys.stderr)
            self.save_file_as()

    def save_file_as(self):
        """Zapisuje plik jako."""
        if not self.exr_data:
            print("[WARN] Próba zapisu bez załadowanych danych", file=sys.stderr)
            return

        print("[INFO] Otwieranie okna dialogowego 'Zapisz jako'", file=sys.stderr)
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Zapisz plik jako...", "", "OpenEXR Files (*.exr)"
        )
        if filepath:
            print(f"[INFO] Wybrano ścieżkę zapisu: {filepath}", file=sys.stderr)
            self._execute_save(filepath)
        else:
            print("[INFO] Anulowano zapis pliku", file=sys.stderr)

    def _execute_save(self, filepath):
        """Uruchamia wątek zapisu pliku."""
        print(f"[INFO] Rozpoczęcie procesu zapisu do: {filepath}", file=sys.stderr)
        # TODO: Implementacja aktualizacji metadanych z tabeli przed zapisem
        # (na razie zapisuje z oryginalnymi metadanymi)
        self.image_preview.setText("Zapisywanie pliku, proszę czekać...")
        QApplication.processEvents()

        self.file_thread = FileOperationThread(
            filepath, operation="save", data_to_save=self.exr_data
        )
        self.file_thread.finished.connect(lambda: self.on_file_saved(filepath))
        self.file_thread.error.connect(self.on_file_error)
        self.file_thread.start()

    def on_file_saved(self, filepath):
        """Obsługuje zakończenie zapisu pliku."""
        print(f"[INFO] Plik został pomyślnie zapisany: {filepath}", file=sys.stderr)
        self.image_preview.setText(f"Plik zapisany pomyślnie w:\n{filepath}")
        # Jeśli 'Zapisz jako', zaktualizuj ścieżkę i tytuł okna
        if self.exr_data and self.exr_data["filepath"] != filepath:
            print(f"[INFO] Zaktualizowano ścieżkę pliku na: {filepath}", file=sys.stderr)
            self.exr_data["filepath"] = filepath
            self.setWindowTitle(f"EXR Editor - {os.path.basename(filepath)}")

    def closeEvent(self, event):
        """Obsługuje zamknięcie aplikacji."""
        print("[INFO] Próba zamknięcia aplikacji", file=sys.stderr)
        print("[INFO] Zamykanie aplikacji...", file=sys.stderr)
        event.accept()

    def resizeEvent(self, event):
        """Obsługuje zmianę rozmiaru okna."""
        # Odśwież podgląd po zmianie rozmiaru okna
        self.update_display()
        super().resizeEvent(event) 