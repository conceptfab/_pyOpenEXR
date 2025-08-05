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


# --- Wątek do asynchronicznego ładowania/zapisu plików ---
# Aby uniknąć blokowania GUI przy dużych plikach
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
        print(f"[INFO] Sprawdzanie czy plik jest prawidłowym plikiem OpenEXR: {self.filepath}", file=sys.stderr)
        if not OpenEXR.isOpenExrFile(self.filepath):
            print(f"[ERROR] Plik nie jest prawidłowym plikiem OpenEXR: {self.filepath}", file=sys.stderr)
            raise ValueError("To nie jest prawidłowy plik OpenEXR.")

        # Używamy InputFile - kompatybilne ze wszystkimi wersjami OpenEXR
        print("[INFO] Używanie InputFile (kompatybilne ze wszystkimi wersjami OpenEXR)", file=sys.stderr)
        input_file = OpenEXR.InputFile(self.filepath)
        header = input_file.header()
        # Obsługa różnych formatów header - może być dict lub obiekt
        if hasattr(header, "dataWindow"):
            dw = header.dataWindow
        else:
            dw = header["dataWindow"]
        size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)

        # Zbuduj pseudo-part
        print(f"[INFO] Rozmiar obrazu: {size[0]}x{size[1]} pikseli", file=sys.stderr)
        loaded_data = {"parts": [], "filepath": self.filepath}
        part_data = {
            "name": "default",
            "header": header,
            "size": size,
            "channels": {},
            "layers": {},
        }

        # Kanały z nagłówka w starszych bindingach: header['channels'] to dict name->Imath.Channel
        # Obsługa różnych formatów header - może być dict lub obiekt
        if hasattr(header, "channels"):
            channel_info = header.channels
        else:
            channel_info = header["channels"]
        # Grupowanie w warstwy
        print(f"[INFO] Znaleziono {len(channel_info)} kanałów", file=sys.stderr)
        for ch_name, ch_info in channel_info.items():
            layer_name = ch_name.split(".")[0] if "." in ch_name else "default"
            part_data["layers"].setdefault(layer_name, []).append(ch_name)

        # Odczyt pikseli dla wszystkich kanałów naraz
        print("[INFO] Odczyt danych pikseli...", file=sys.stderr)
        channel_names = list(channel_info.keys())
        print(f"[DEBUG] Nazwy kanałów do odczytu: {channel_names}", file=sys.stderr)
        
        # Próbuj różne metody odczytu danych
        pixels_dict = {}
        try:
            pixels_data = input_file.channels(channel_names)
            print(f"[DEBUG] Typ zwróconych danych: {type(pixels_data)}", file=sys.stderr)
            if isinstance(pixels_data, list):
                print(f"[DEBUG] Długość listy danych: {len(pixels_data)}", file=sys.stderr)
            elif isinstance(pixels_data, dict):
                print(f"[DEBUG] Klucze w słowniku: {list(pixels_data.keys())}", file=sys.stderr)
            
            # Sprawdź czy pixels_data to słownik czy lista
            if isinstance(pixels_data, dict):
                pixels_dict = pixels_data
            else:
                # Jeśli to lista, utwórz słownik mapujący nazwy kanałów na dane
                for i, ch_name in enumerate(channel_names):
                    if i < len(pixels_data):
                        pixels_dict[ch_name] = pixels_data[i]
                    else:
                        print(f"[WARN] Brak danych dla kanału: {ch_name}", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] Błąd przy odczycie wszystkich kanałów naraz: {e}", file=sys.stderr)
            print("[INFO] Próbuję odczytać kanały pojedynczo...", file=sys.stderr)
            # Fallback: odczyt kanałów pojedynczo
            for ch_name in channel_names:
                try:
                    pixels_dict[ch_name] = input_file.channel(ch_name)
                    print(f"[DEBUG] Pojedynczo załadowano kanał: {ch_name}", file=sys.stderr)
                except Exception as ch_error:
                    print(f"[ERROR] Nie udało się załadować kanału {ch_name}: {ch_error}", file=sys.stderr)

        for ch_name in channel_names:
            if ch_name not in pixels_dict:
                print(f"[WARN] Pomijam kanał bez danych: {ch_name}", file=sys.stderr)
                continue
            
            if pixels_dict[ch_name] is None:
                print(f"[WARN] Kanał {ch_name} ma puste dane", file=sys.stderr)
                continue
                
            ch_info = channel_info[ch_name]
            # Ustal dtype na podstawie typu piksela
            if ch_info.type == Imath.PixelType(Imath.PixelType.FLOAT):
                dtype = np.float32
            elif ch_info.type == Imath.PixelType(Imath.PixelType.UINT):
                dtype = np.uint32
            else:
                dtype = np.float16
            
            try:
                arr = np.frombuffer(pixels_dict[ch_name], dtype=dtype)
                arr.shape = (size[1], size[0])
                part_data["channels"][ch_name] = arr
                print(f"[DEBUG] Załadowano kanał: {ch_name} (typ: {dtype})", file=sys.stderr)
            except Exception as e:
                print(f"[ERROR] Błąd przy przetwarzaniu kanału {ch_name}: {e}", file=sys.stderr)
                continue

        loaded_data["parts"].append(part_data)
        print("[INFO] Zakończono przetwarzanie części default", file=sys.stderr)
        return loaded_data

    def _save_exr(self):
        """Zapisuje dane do pliku EXR."""
        headers = []
        parts_data = []

        for part_info in self.data_to_save["parts"]:
            header = OpenEXR.Header(part_info["size"][0], part_info["size"][1])
            # Kopiuj/zaktualizuj metadane
            original_header = part_info["header"]
            for key, value in original_header.items():
                header[key] = value

            # Przygotuj dane kanałów do zapisu
            channels_to_write = {}
            for ch_name, np_array in part_info["channels"].items():
                channels_to_write[ch_name] = np_array.tobytes()

            headers.append(header)
            parts_data.append(channels_to_write)

        exr_output = OpenEXR.MultiPartOutputFile(self.filepath, headers)
        exr_output.writePixels(parts_data)


# --- Główna klasa aplikacji ---
class EXREditor(QMainWindow):
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
        # Główny widget i layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Splitter do zmiany rozmiarów paneli
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- Panel lewy: Nawigacja (Drzewo) ---
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Element", "Typ"])
        self.tree_widget.setColumnWidth(0, 200)
        self.tree_widget.currentItemChanged.connect(self.on_tree_item_selected)
        splitter.addWidget(self.tree_widget)

        # --- Panel centralny i prawy w jednym kontenerze ---
        right_container = QSplitter(Qt.Orientation.Vertical)

        # --- Panel centralny: Podgląd obrazu ---
        self.image_preview = QLabel("Otwórz plik .exr, aby rozpocząć")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumSize(400, 300)
        right_container.addWidget(self.image_preview)

        # --- Panel prawy: Edycja i metadane ---
        self.tabs = QTabWidget()

        # Zakładka 1: Kontrolki edycji
        edit_widget = QWidget()
        edit_layout = QFormLayout(edit_widget)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.update_display)

        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(0, 300)  # 100 = 1.0
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self.update_display)

        edit_layout.addRow("Jasność:", self.brightness_slider)
        edit_layout.addRow("Kontrast:", self.contrast_slider)
        self.tabs.addTab(edit_widget, "Kontrolki podglądu")

        # Zakładka 2: Metadane
        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Atrybut", "Wartość"])
        self.metadata_table.setColumnWidth(0, 150)
        self.metadata_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.metadata_table, "Metadane")

        right_container.addWidget(self.tabs)
        splitter.addWidget(right_container)

        splitter.setSizes([300, 1300])
        right_container.setSizes([600, 300])

    def _create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Plik")

        open_action = QAction("&Otwórz...", self)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        save_action = QAction("&Zapisz", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("Zapisz &jako...", self)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("&Wyjdź", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def open_file_dialog(self):
        print("[INFO] Otwieranie okna dialogowego wyboru pliku", file=sys.stderr)
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Otwórz plik OpenEXR", "", "OpenEXR Files (*.exr)"
        )
        if filepath:
            print(f"[INFO] Wybrano plik do załadowania: {filepath}", file=sys.stderr)
            self.image_preview.setText("Ładowanie pliku, proszę czekać...")
            QApplication.processEvents()  # Odśwież UI
            self.file_thread = FileOperationThread(filepath, operation="load")
            self.file_thread.finished.connect(self.on_file_loaded)
            self.file_thread.error.connect(self.on_file_error)
            self.file_thread.start()
        else:
            print("[INFO] Anulowano wybór pliku", file=sys.stderr)

    def on_file_loaded(self, loaded_data):
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
        self.populate_tree()
        self.image_preview.setText("Wybierz element z drzewa, aby wyświetlić podgląd.")
        print(f"[INFO] Zaktualizowano interfejs dla pliku: {self.exr_data.get('filepath', '')}", file=sys.stderr)

    def on_file_error(self, error_message):
        # Tylko log do konsoli – bez komunikatów w UI
        print(f"[ERROR] Błąd podczas operacji na pliku: {error_message}", file=sys.stderr)
        self.image_preview.setText("Nie udało się załadować pliku.")

    def populate_tree(self):
        print("[INFO] Aktualizacja drzewa nawigacji", file=sys.stderr)
        self.tree_widget.clear()
        if not self.exr_data:
            print("[WARN] Brak danych EXR do wyświetlenia w drzewie", file=sys.stderr)
            return

        filepath = self.exr_data.get("filepath", "")
        file_item = QTreeWidgetItem(
            self.tree_widget, [os.path.basename(filepath), "Plik"]
        )

        parts_iter = self.exr_data.get("parts", [])
        for i, part_data in enumerate(parts_iter):
            part_name = part_data.get("name", "default")
            layers = part_data.get("layers", {})
            print(f"[DEBUG] Dodawanie części do drzewa: {part_name}", file=sys.stderr)

            part_item = QTreeWidgetItem(file_item, [part_name, "Part"])
            part_item.setData(
                0, Qt.ItemDataRole.UserRole, ("part", i)
            )

            for layer_name, channel_list in layers.items():
                print(f"[DEBUG] Dodawanie warstwy do drzewa: {layer_name} ({len(channel_list)} kanałów)", file=sys.stderr)
                layer_item = QTreeWidgetItem(part_item, [layer_name, "Warstwa"])
                layer_item.setData(
                    0, Qt.ItemDataRole.UserRole, ("layer", i, layer_name)
                )

                for ch_name in channel_list:
                    ch_name_s = str(ch_name)
                    channel_item = QTreeWidgetItem(layer_item, [ch_name_s, "Kanał"])
                    channel_item.setData(
                        0, Qt.ItemDataRole.UserRole, ("channel", i, ch_name_s)
                    )

        self.tree_widget.expandAll()
        print("[INFO] Drzewo nawigacji zostało zaktualizowane", file=sys.stderr)

    def on_tree_item_selected(self, current_item, previous_item):
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
        size = part_data.get("size", (0, 0))
        channels = part_data.get("channels", {})
        layers = part_data.get("layers", {})

        self.update_metadata_table(header)

        width, height = size
        self.current_preview_data = None

        # Wybór danych do podglądu
        if item_type == "layer":
            layer_name = rest[0]
            layer_channels = layers.get(layer_name, [])
            print(f"[INFO] Przygotowanie podglądu warstwy: {layer_name} ({len(layer_channels)} kanałów)", file=sys.stderr)

            # Spróbuj znaleźć kanały RGB(A)
            r_ch = next((ch for ch in layer_channels if isinstance(ch, str) and ch.endswith(".R")), None)
            g_ch = next((ch for ch in layer_channels if isinstance(ch, str) and ch.endswith(".G")), None)
            b_ch = next((ch for ch in layer_channels if isinstance(ch, str) and ch.endswith(".B")), None)
            a_ch = next((ch for ch in layer_channels if isinstance(ch, str) and ch.endswith(".A")), None)

            if r_ch and g_ch and b_ch:
                print(f"[INFO] Znaleziono kanały RGB: {r_ch}, {g_ch}, {b_ch}", file=sys.stderr)
                r = channels.get(r_ch)
                g = channels.get(g_ch)
                b = channels.get(b_ch)
                if r is not None and g is not None and b is not None:
                    a = channels.get(a_ch, np.ones_like(r))
                    self.current_preview_data = np.stack([r, g, b, a], axis=-1)
            if self.current_preview_data is None:
                # Jeśli nie ma RGB, pokaż pierwszy kanał z warstwy
                if layer_channels:
                    ch_name = str(layer_channels[0])
                    print(f"[INFO] Brak kanałów RGB, używam pierwszego kanału: {ch_name}", file=sys.stderr)
                    self.current_preview_data = channels.get(ch_name)

        elif item_type == "channel":
            ch_name = str(rest[0])
            print(f"[INFO] Przygotowanie podglądu kanału: {ch_name}", file=sys.stderr)
            self.current_preview_data = channels.get(ch_name)

        # Zresetuj suwaki i odśwież podgląd
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(100)
        self.update_display()

    def update_display(self):
        """Konwertuje dane float na obraz 8-bitowy i wyświetla go."""
        if self.current_preview_data is None:
            self.image_preview.clear()
            return

        # Pobierz wartości z suwaków
        brightness = self.brightness_slider.value() / 100.0
        contrast = self.contrast_slider.value() / 100.0

        # Kopiuj dane, aby nie modyfikować oryginału
        display_data = self.current_preview_data.copy()

        # Prosta edycja podglądu (nie modyfikuje danych źródłowych EXR)
        display_data = (display_data - 0.5) * contrast + 0.5 + brightness

        # Prosty tone mapping i konwersja do 8-bit
        # Stosujemy `clip`, aby uniknąć błędów przy konwersji
        display_data = np.clip(display_data, 0.0, 1.0)
        img_8bit = (display_data * 255).astype(np.uint8)

        height, width = img_8bit.shape[:2]

        if img_8bit.ndim == 3:  # Obraz kolorowy (RGBA)
            q_image_format = QImage.Format.Format_RGBA8888
            bytes_per_line = 4 * width
        else:  # Skala szarości
            q_image_format = QImage.Format.Format_Grayscale8
            bytes_per_line = 1 * width

        # Tworzenie QImage z numpy array
        q_image = QImage(img_8bit.data, width, height, bytes_per_line, q_image_format)

        # QImage musi mieć własną kopię danych, inaczej może dojść do błędu segmentacji
        q_image = q_image.copy()

        pixmap = QPixmap.fromImage(q_image)
        self.image_preview.setPixmap(
            pixmap.scaled(
                self.image_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def update_metadata_table(self, header):
        self.metadata_table.setRowCount(0)
        for key, value in header.items():
            row_position = self.metadata_table.rowCount()
            self.metadata_table.insertRow(row_position)
            self.metadata_table.setItem(row_position, 0, QTableWidgetItem(str(key)))
            self.metadata_table.setItem(row_position, 1, QTableWidgetItem(str(value)))

    def save_file(self):
        if self.exr_data and self.exr_data.get("filepath"):
            print(f"[INFO] Zapisywanie pliku: {self.exr_data['filepath']}", file=sys.stderr)
            self._execute_save(self.exr_data["filepath"])
        else:
            print("[INFO] Brak ścieżki pliku, otwieranie okna 'Zapisz jako'", file=sys.stderr)
            self.save_file_as()

    def save_file_as(self):
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
        print(f"[INFO] Plik został pomyślnie zapisany: {filepath}", file=sys.stderr)
        self.image_preview.setText(f"Plik zapisany pomyślnie w:\n{filepath}")
        # Jeśli 'Zapisz jako', zaktualizuj ścieżkę i tytuł okna
        if self.exr_data and self.exr_data["filepath"] != filepath:
            print(f"[INFO] Zaktualizowano ścieżkę pliku na: {filepath}", file=sys.stderr)
            self.exr_data["filepath"] = filepath
            self.setWindowTitle(f"EXR Editor - {os.path.basename(filepath)}")

    def closeEvent(self, event):
        print("[INFO] Próba zamknięcia aplikacji", file=sys.stderr)
        # Zamykamy bez modala – tylko konsola
        print("[INFO] Zamykanie aplikacji...", file=sys.stderr)
        event.accept()

    def resizeEvent(self, event):
        # Odśwież podgląd po zmianie rozmiaru okna
        self.update_display()
        super().resizeEvent(event)


if __name__ == "__main__":
    print("[INFO] Uruchamianie aplikacji EXR Editor", file=sys.stderr)
    app = QApplication(sys.argv)
    editor = EXREditor()
    editor.show()
    print("[INFO] Aplikacja została uruchomiona pomyślnie", file=sys.stderr)
    sys.exit(app.exec())
