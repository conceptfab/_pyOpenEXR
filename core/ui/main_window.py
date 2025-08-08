"""
Główne okno aplikacji EXR Editor.
"""

import sys
import os
import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QFileDialog, QApplication, QListWidgetItem
from PyQt6.QtGui import QIcon, QPixmap

from .components import (
    TreeNavigator, ImagePreview, ControlPanel, 
    MetadataPanel, TabManager, MenuManager, FileBrowser
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
        self.original_linear_data = None  # Oryginalne dane liniowe dla ekspozycji/gammy
        self.file_thread = None
        self.working_directory = None  # Folder roboczy dla przeglądarki plików
        self.thumbnail_cache = {}  # Cache dla miniatur

        self._init_ui()
        self._create_menus()
        print("[INFO] Aplikacja została zainicjalizowana pomyślnie", file=sys.stderr)

    def _init_ui(self):
        """Inicjalizuje interfejs użytkownika."""
        # Główny widget i layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Główny splitter do zmiany rozmiarów paneli (lewy | środek | prawy)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)

        # --- Panel lewy: Nawigacja (Drzewo) ---
        self.tree_widget = TreeNavigator.create_tree_widget()
        self.tree_widget.currentItemChanged.connect(self.on_tree_item_selected)
        main_splitter.addWidget(self.tree_widget)

        # --- Panel środkowy: Kontener z podglądem i kontrolkami ---
        middle_container = QSplitter(Qt.Orientation.Vertical)

        # Podgląd obrazu
        self.image_preview = ImagePreview.create_preview_widget()
        middle_container.addWidget(self.image_preview)

        # Kontrolki edycji i metadane
        (self.control_widget, self.brightness_slider, self.contrast_slider, self.exposure_slider, self.gamma_slider,
         self.brightness_spinbox, self.contrast_spinbox, self.exposure_spinbox, self.gamma_spinbox) = ControlPanel.create_control_widget()
        
        # Połącz suwaki z update_display
        self.brightness_slider.valueChanged.connect(self.update_display)
        self.contrast_slider.valueChanged.connect(self.update_display)
        self.exposure_slider.valueChanged.connect(self.update_display)
        self.gamma_slider.valueChanged.connect(self.update_display)
        
        # Połącz spinboxy z update_display
        self.brightness_spinbox.valueChanged.connect(self.update_display)
        self.contrast_spinbox.valueChanged.connect(self.update_display)
        self.exposure_spinbox.valueChanged.connect(self.update_display)
        self.gamma_spinbox.valueChanged.connect(self.update_display)

        self.metadata_table = MetadataPanel.create_metadata_widget()
        self.tabs = TabManager.create_tab_widget(self.control_widget, self.metadata_table)

        middle_container.addWidget(self.tabs)
        main_splitter.addWidget(middle_container)

        # --- Panel prawy: Przeglądarka plików EXR ---
        self.file_browser_widget, self.file_list, self.file_info_label, self.folder_button = FileBrowser.create_file_browser_widget()
        self.file_list.itemClicked.connect(self.on_file_selected)
        self.folder_button.clicked.connect(self.open_working_folder)
        main_splitter.addWidget(self.file_browser_widget)

        # Ustaw proporcje paneli: drzewo(300) | główny(1000) | przeglądarka(300)
        main_splitter.setSizes([300, 1000, 300])
        middle_container.setSizes([600, 300])

    def _create_menus(self):
        """Tworzy pasek menu."""
        MenuManager.create_menu_bar(
            self, 
            self.open_file_dialog, 
            self.save_file, 
            self.save_file_as,
            self.open_working_folder
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
                data = EXRReader.read_exr_file_cached(filepath)
                self.on_file_loaded(data)
                
                # AUTOMATYCZNY PODGLĄD RGB PO ZAŁADOWANIU PLIKU
                self.auto_display_rgb_preview()
                
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
        channels_data = part_data.get("channels", {})
        MetadataHandler.populate_metadata_table(self.metadata_table, header, channels_data)

        self.current_preview_data = None
        self.original_linear_data = None

        # Wybór danych do podglądu
        if item_type == "layer":
            layer_name = rest[0]
            # Sprawdź czy warstwa ma kanały RGB i automatycznie wyświetl podgląd RGB
            if self._layer_has_rgb_channels(part_data, layer_name):
                print(f"[INFO] Warstwa {layer_name} ma kanały RGB - automatyczny podgląd RGB", file=sys.stderr)
                # Dla RGB zapisz oryginalne dane liniowe
                self.original_linear_data = ImageProcessor.prepare_rgb_preview_linear(
                    part_data, layer_name=layer_name
                )
                # I przygotuj wersję do wyświetlenia
                self.current_preview_data = ImageProcessor.prepare_rgb_preview(
                    part_data, layer_name=layer_name
                )
            else:
                # Jeśli brak RGB, użyj standardowego podglądu warstwy
                self.current_preview_data = ImageProcessor.prepare_preview_data(
                    part_data, "layer", layer_name=layer_name
                )
        elif item_type == "rgb_preview":
            layer_name = rest[0]
            # Dla RGB zapisz oryginalne dane liniowe
            self.original_linear_data = ImageProcessor.prepare_rgb_preview_linear(
                part_data, layer_name=layer_name
            )
            # I przygotuj wersję do wyświetlenia
            self.current_preview_data = ImageProcessor.prepare_rgb_preview(
                part_data, layer_name=layer_name
            )
        elif item_type == "channel":
            ch_name = str(rest[0])
            self.current_preview_data = ImageProcessor.prepare_preview_data(
                part_data, "channel", channel_name=ch_name
            )

        # Zresetuj suwaki i spinboxy, potem odśwież podgląd
        self.brightness_slider.setValue(0)
        self.brightness_spinbox.setValue(0.0)
        self.contrast_slider.setValue(100)
        self.contrast_spinbox.setValue(1.0)
        self.exposure_slider.setValue(0)
        self.exposure_spinbox.setValue(0.0)
        self.gamma_slider.setValue(220)  # 2.2
        self.gamma_spinbox.setValue(2.2)
        self.update_display()

    def _layer_has_rgb_channels(self, part_data, layer_name):
        """
        Sprawdza czy warstwa ma kanały RGB.
        
        Args:
            part_data (dict): Dane części pliku EXR
            layer_name (str): Nazwa warstwy
            
        Returns:
            bool: True jeśli warstwa ma kanały R, G, B
        """
        layers = part_data.get("layers", {})
        layer_channels = layers.get(layer_name, [])
        
        # Szukaj kanałów R, G, B
        has_r = any(str(ch).endswith('.R') or str(ch) == 'R' or str(ch).endswith('.red') or str(ch).lower().endswith('red') for ch in layer_channels)
        has_g = any(str(ch).endswith('.G') or str(ch) == 'G' or str(ch).endswith('.green') or str(ch).lower().endswith('green') for ch in layer_channels)
        has_b = any(str(ch).endswith('.B') or str(ch) == 'B' or str(ch).endswith('.blue') or str(ch).lower().endswith('blue') for ch in layer_channels)
        
        return has_r and has_g and has_b

    def update_display(self):
        """Aktualizuje wyświetlanie obrazu z optymalizacjami."""
        if self.current_preview_data is None:
            self.image_preview.clear()
            return

        # Cache ostatnich wartości, aby uniknąć niepotrzebnych przeliczeń
        if not hasattr(self, '_last_display_params'):
            self._last_display_params = None
            
        # Pobierz wartości z suwaków
        brightness = self.brightness_slider.value() / 100.0
        contrast = self.contrast_slider.value() / 100.0
        exposure = self.exposure_slider.value() / 100.0  # -5.0 do +5.0
        gamma = self.gamma_slider.value() / 100.0  # 0.5 do 5.0
        
        current_params = (brightness, contrast, exposure, gamma)
        
        # Jeśli parametry się nie zmieniły, nie przeliczaj
        if self._last_display_params == current_params:
            return
            
        self._last_display_params = current_params

        # Sprawdź czy mamy oryginalne dane liniowe (dla RGB)
        if self.original_linear_data is not None:
            # Zastosuj ekspozycję i gamma na oryginalnych danych liniowych
            processed_data = ImageProcessor.apply_color_correction(
                self.original_linear_data, exposure, gamma
            )
            # Następnie zastosuj pozostałe korekty
            adjusted_data = ImageProcessor.apply_display_adjustments(
                processed_data, brightness, contrast
            )
        else:
            # Dla pojedynczych kanałów zastosuj tylko podstawowe korekty
            adjusted_data = ImageProcessor.apply_display_adjustments(
                self.current_preview_data, brightness, contrast
            )
        
        q_image = ImageProcessor.numpy_to_qimage(adjusted_data)
        pixmap = ImageProcessor.create_scaled_pixmap(q_image, self.image_preview.size())
        
        if pixmap:
            self.image_preview.setPixmap(pixmap)

    def open_working_folder(self):
        """Otwiera okno dialogowe wyboru folderu roboczego."""
        print("[INFO] Otwieranie okna dialogowego wyboru folderu roboczego", file=sys.stderr)
        folder_path = QFileDialog.getExistingDirectory(
            self, "Wybierz folder roboczy z plikami EXR", ""
        )
        if folder_path:
            print(f"[INFO] Wybrano folder roboczy: {folder_path}", file=sys.stderr)
            self.working_directory = folder_path
            self.populate_file_browser()

    def populate_file_browser(self):
        """Wielowątkowa wersja generowania miniatur."""
        if not self.working_directory:
            return
            
        print(f"[INFO] Skanowanie folderu: {self.working_directory}", file=sys.stderr)
        self.file_list.clear()
        
        # Znajdź pliki EXR
        exr_files = []
        try:
            for file_name in os.listdir(self.working_directory):
                if file_name.lower().endswith('.exr'):
                    file_path = os.path.join(self.working_directory, file_name)
                    exr_files.append((file_name, file_path))
        except Exception as e:
            print(f"[ERROR] Błąd podczas skanowania folderu: {e}", file=sys.stderr)
            self.file_info_label.setText(f"Błąd podczas skanowania folderu: {e}")
            self.file_info_label.show()
            return
        
        if not exr_files:
            self.file_info_label.setText("Brak plików EXR w wybranym folderze")
            self.file_info_label.show()
            return
            
        self.file_info_label.setText(f"Znaleziono {len(exr_files)} plików EXR")
        self.file_info_label.show()
        
        # Generuj miniatury wielowątkowo
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.generate_thumbnail, fp): (fn, fp) 
                      for fn, fp in exr_files}
            
            for future in concurrent.futures.as_completed(futures):
                file_name, file_path = futures[future]
                try:
                    thumbnail = future.result()
                    self.add_file_to_browser_with_thumbnail(file_name, file_path, thumbnail)
                except Exception as e:
                    print(f"[ERROR] Błąd miniaturki {file_name}: {e}", file=sys.stderr)

    def add_file_to_browser(self, file_name, file_path):
        """Dodaje plik do przeglądarki z miniaturą."""
        try:
            # Generuj miniaturę
            thumbnail = self.generate_thumbnail(file_path)
            self.add_file_to_browser_with_thumbnail(file_name, file_path, thumbnail)
        except Exception as e:
            print(f"[ERROR] Błąd podczas dodawania pliku {file_name}: {e}", file=sys.stderr)
    
    def add_file_to_browser_with_thumbnail(self, file_name, file_path, thumbnail):
        """Dodaje plik do przeglądarki z gotową miniaturą."""
        try:
            # Stwórz element listy
            item = QListWidgetItem()
            item.setText(file_name)
            item.setIcon(QIcon(thumbnail))
            item.setData(Qt.ItemDataRole.UserRole, file_path)  # Przechowaj ścieżkę pliku
            
            # Dodaj tooltip z informacjami o pliku
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            tooltip = f"Plik: {file_name}\nRozmiar: {file_size_mb:.1f} MB\nŚcieżka: {file_path}"
            item.setToolTip(tooltip)
            
            self.file_list.addItem(item)
            
        except Exception as e:
            print(f"[ERROR] Błąd podczas dodawania pliku {file_name}: {e}", file=sys.stderr)

    def generate_thumbnail(self, file_path):
        """Generuje miniaturę pliku EXR z cache'owaniem."""
        
        # Sprawdź cache miniatur
        if file_path in self.thumbnail_cache:
            return self.thumbnail_cache[file_path]
            
        try:
            # Spróbuj załadować podstawowe informacje o pliku
            from core.file_operations.exr_reader import EXRReader
            
            # Sprawdź czy to prawidłowy plik EXR
            if not EXRReader.is_valid_exr_file(file_path):
                thumbnail = self.create_error_thumbnail("Nieprawidłowy plik EXR")
                self.thumbnail_cache[file_path] = thumbnail
                return thumbnail
            
            # Wczytaj dane EXR z cache'em dla szybkości
            data = EXRReader.read_exr_file_cached(file_path)
            
            if not data or not data.get("parts"):
                return self.create_error_thumbnail("Brak danych")
            
            part_data = data["parts"][0]
            
            # Spróbuj wygenerować podgląd RGB
            # Znajdź warstwę z kanałami RGB (zazwyczaj "Beauty" lub pierwsza dostępna)
            layers = part_data.get("layers", {})
            rgb_layer = None
            
            # Najpierw sprawdź "Beauty" (nowa nazwa), potem "default" (dla starych plików)
            for layer_name in ["Beauty", "default"]:
                if layer_name in layers:
                    rgb_layer = layer_name
                    break
            
            # Jeśli nie znaleziono, weź pierwszą dostępną warstwę
            if not rgb_layer and layers:
                rgb_layer = list(layers.keys())[0]
            
            preview_data = None
            if rgb_layer:
                preview_data = ImageProcessor.prepare_rgb_preview(part_data, rgb_layer)
            
            if preview_data is not None:
                # Konwertuj na QPixmap i przeskaluj do rozmiaru miniatury
                q_image = ImageProcessor.numpy_to_qimage(preview_data)
                if q_image:
                    pixmap = QPixmap.fromImage(q_image)
                    # Przeskaluj do rozmiaru miniatury (100x100)
                    thumbnail = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, 
                                            Qt.TransformationMode.SmoothTransformation)
                    # Cache'uj miniaturę
                    self.thumbnail_cache[file_path] = thumbnail
                    return thumbnail
            
            # Jeśli nie udało się wygenerować RGB, spróbuj pierwszy kanał
            channels = part_data.get("channels", {})
            if channels:
                first_channel_name = list(channels.keys())[0]
                channel_data = ImageProcessor.prepare_preview_data(
                    part_data, "channel", channel_name=first_channel_name
                )
                if channel_data is not None:
                    adjusted_data = ImageProcessor.apply_display_adjustments(channel_data, 0.0, 1.0)
                    q_image = ImageProcessor.numpy_to_qimage(adjusted_data)
                    if q_image:
                        pixmap = QPixmap.fromImage(q_image)
                        thumbnail = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
                        # Cache'uj miniaturę
                        self.thumbnail_cache[file_path] = thumbnail
                        return thumbnail
            
            thumbnail = self.create_error_thumbnail("Brak podglądu")
            self.thumbnail_cache[file_path] = thumbnail
            return thumbnail
            
        except Exception as e:
            print(f"[ERROR] Błąd podczas generowania miniatury dla {file_path}: {e}", file=sys.stderr)
            thumbnail = self.create_error_thumbnail(f"Błąd: {str(e)[:20]}")
            self.thumbnail_cache[file_path] = thumbnail
            return thumbnail

    def create_error_thumbnail(self, error_text):
        """Tworzy miniaturę błędu."""
        pixmap = QPixmap(100, 100)
        pixmap.fill(Qt.GlobalColor.lightGray)
        return pixmap

    def on_file_selected(self, item):
        """Obsługuje wybór pliku z przeglądarki."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            print(f"[INFO] Wybrano plik z przeglądarki: {file_path}", file=sys.stderr)
            self.load_file_from_path(file_path)

    def load_file_from_path(self, filepath):
        """Ładuje plik EXR z podanej ścieżki i automatycznie wyświetla podgląd RGB."""
        try:
            self.image_preview.setText("Ładowanie pliku, proszę czekać...")
            QApplication.processEvents()
            
            from core.file_operations.exr_reader import EXRReader
            data = EXRReader.read_exr_file_cached(filepath)
            self.on_file_loaded(data)
            
            # AUTOMATYCZNY PODGLĄD RGB PO ZAŁADOWANIU PLIKU
            self.auto_display_rgb_preview()
            
        except Exception as e:
            print(f"[ERROR] Błąd podczas ładowania pliku: {e}", file=sys.stderr)
            self.image_preview.setText("Nie udało się załadować pliku.")

    def auto_display_rgb_preview(self):
        """Automatycznie wyświetla podgląd RGB dla pierwszej warstwy z kanałami RGB."""
        if not self.exr_data or not self.exr_data.get("parts"):
            return
            
        print("[INFO] Szukanie warstwy RGB do automatycznego podglądu", file=sys.stderr)
        
        # Sprawdź pierwszą część
        part_data = self.exr_data["parts"][0]
        layers = part_data.get("layers", {})
        
        # Znajdź pierwszą warstwę z kanałami RGB
        for layer_name, channels in layers.items():
            if self._layer_has_rgb_channels(part_data, layer_name):
                print(f"[INFO] Automatyczny podgląd RGB dla warstwy: {layer_name}", file=sys.stderr)
                
                # Załaduj dane liniowe dla ekspozycji/gammy
                self.original_linear_data = ImageProcessor.prepare_rgb_preview_linear(
                    part_data, layer_name=layer_name
                )
                
                # Przygotuj podgląd RGB
                self.current_preview_data = ImageProcessor.prepare_rgb_preview(
                    part_data, layer_name=layer_name
                )
                
                # Zresetuj suwaki i wyświetl
                self.brightness_slider.setValue(0)
                self.brightness_spinbox.setValue(0.0)
                self.contrast_slider.setValue(100)
                self.contrast_spinbox.setValue(1.0)
                self.exposure_slider.setValue(0)
                self.exposure_spinbox.setValue(0.0)
                self.gamma_slider.setValue(220)  # 2.2
                self.gamma_spinbox.setValue(2.2)
                
                # Odśwież podgląd
                self.update_display()
                return
        
        print("[INFO] Brak warstw RGB - pozostaje bez automatycznego podglądu", file=sys.stderr)

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