import sys
import logging
import Imath
import numpy as np
import OpenEXR
from PyQt6.QtCore import QThread, pyqtSignal


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

        # Obsługa różnych wersji modułu OpenEXR:
        # - starsze buildy (pypi-openexr) nie mają MultiPartInputFile/parts()
        # - nowsze buildy mogą wspierać multipart, ale Twój błąd wskazuje na brak tej klasy
        if hasattr(OpenEXR, "MultiPartInputFile"):
            print("[INFO] Używanie MultiPartInputFile (nowsza wersja OpenEXR)", file=sys.stderr)
            exr_file = OpenEXR.MultiPartInputFile(self.filepath)
            parts = exr_file.parts()
            part_getter = lambda idx: exr_file.get_part(idx)
            multipart = True
        else:
            # Fallback: Single-part odczyt przy użyciu InputFile
            # Emulujemy strukturę multipart z jedną częścią "default"
            print("[INFO] Używanie InputFile (starsza wersja OpenEXR)", file=sys.stderr)
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

        print(f"[INFO] Znaleziono {len(parts)} części w pliku EXR", file=sys.stderr)
        loaded_data = {"parts": [], "filepath": self.filepath}

        for i, part_name in enumerate(parts):
            print(f"[INFO] Przetwarzanie części {i+1}/{len(parts)}: {part_name}", file=sys.stderr)
            part = part_getter(i)
            header = part.header()
            # Obsługa różnych formatów header - może być dict lub obiekt
            if hasattr(header, "dataWindow"):
                dw = header.dataWindow
            else:
                dw = header["dataWindow"]
            size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)
            print(f"[INFO] Rozmiar części {part_name}: {size[0]}x{size[1]} pikseli", file=sys.stderr)

            part_data = {
                "name": part_name,
                "header": header,
                "size": size,
                "channels": {},
                "layers": {},
            }

            # Grupuj kanały w warstwy
            # W multipart API bywa header.channels() (dict), w niektórych buildach header['channels']
            channel_info = header.channels() if hasattr(header, "channels") else header["channels"]
            print(f"[INFO] Znaleziono {len(channel_info)} kanałów w części {part_name}", file=sys.stderr)
            for ch_name, ch_info in channel_info.items():
                # Przetwarzanie nazwy warstwy (np. "Beauty.R" -> "Beauty")
                layer_name = ch_name.split(".")[0] if "." in ch_name else "default"
                if layer_name not in part_data["layers"]:
                    part_data["layers"][layer_name] = []
                part_data["layers"][layer_name].append(ch_name)

            # Odczytaj dane pikseli dla wszystkich kanałów w tym parcie
            # W multipart API: part.pixels(), w starszych fallback już zwrócił wcześniej
            print(f"[INFO] Odczyt danych pikseli dla części {part_name}...", file=sys.stderr)
            pixel_data = part.pixels()
            for ch_name, ch_info in channel_info.items():
                # Konwertuj dane z bytestring na numpy array
                dtype = np.float16
                if ch_info.type == Imath.PixelType(Imath.PixelType.FLOAT):
                    dtype = np.float32
                elif ch_info.type == Imath.PixelType(Imath.PixelType.UINT):
                    dtype = np.uint32

                arr = np.frombuffer(pixel_data[ch_name], dtype=dtype)
                arr.shape = (size[1], size[0])
                part_data["channels"][ch_name] = arr
                print(f"[DEBUG] Załadowano kanał: {ch_name} (typ: {dtype})", file=sys.stderr)

            loaded_data["parts"].append(part_data)
            print(f"[INFO] Zakończono przetwarzanie części {part_name}", file=sys.stderr)

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
