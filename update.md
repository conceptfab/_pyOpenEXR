Optymalizacje w istniejącym kodzie Python
1. Optymalizacje w przetwarzaniu obrazów
Plik: core/data_processing/image_processor.py
python# W funkcji apply_color_correction - dodaj cache'owanie operacji
@staticmethod
@lru_cache(maxsize=128)
def _cached_gamma_correction(gamma_value):
    """Cache'uje obliczenia gamma dla często używanych wartości."""
    return 1.0 / np.clip(gamma_value, 0.01, 10.0)

@staticmethod
def apply_color_correction(linear_image, exposure=0.0, gamma=2.2):
    """
    Zoptymalizowana wersja z wykorzystaniem vectorization i cache.
    """
    if linear_image is None:
        return None
        
    # Użyj numba JIT dla krytycznych operacji
    return ImageProcessor._apply_correction_numba(linear_image, exposure, gamma)

@staticmethod
@numba.jit(nopython=True, parallel=True)
def _apply_correction_numba(linear_image, exposure, gamma):
    """JIT-kompilowana wersja korekcji kolorów."""
    # Zabezpiecz dane
    safe_linear = np.clip(linear_image, 0.0, 100.0)
    
    # Ekspozycja (vectorized)
    exposure_factor = 2.0 ** np.clip(exposure, -10.0, 10.0)
    exposed_image = safe_linear * exposure_factor
    
    # Gamma (vectorized)
    safe_gamma = np.clip(gamma, 0.01, 10.0)
    gamma_inv = 1.0 / safe_gamma
    gammad_image = np.power(np.clip(exposed_image, 0.0, 100.0), gamma_inv)
    
    # Konwersja do uint8
    return (np.clip(gammad_image, 0.0, 1.0) * 255).astype(np.uint8)
2. Optymalizacje ładowania plików EXR
Plik: core/file_operations/exr_reader.py
python# Dodaj lazy loading i cache'owanie
class EXRReader:
    _file_cache = {}
    _thumbnail_cache = {}
    
    @staticmethod
    def read_exr_file_cached(filepath):
        """Wersja z cache'owaniem dla często używanych plików."""
        if filepath in EXRReader._file_cache:
            return EXRReader._file_cache[filepath]
        
        data = EXRReader.read_exr_file(filepath)
        EXRReader._file_cache[filepath] = data
        return data
    
    @staticmethod
    @numba.jit(nopython=True)
    def _process_channel_data_fast(raw_data, dtype, shape):
        """JIT-kompilowana konwersja danych kanałów."""
        arr = np.frombuffer(raw_data, dtype=dtype)
        return arr.reshape(shape)
3. Optymalizacje generowania miniatur
Plik: core/ui/main_window.py
python# Dodaj wielowątkowe generowanie miniatur
from concurrent.futures import ThreadPoolExecutor

def populate_file_browser(self):
    """Wielowątkowa wersja generowania miniatur."""
    if not self.working_directory:
        return
        
    self.file_list.clear()
    
    # Znajdź pliki EXR
    exr_files = []
    for file_name in os.listdir(self.working_directory):
        if file_name.lower().endswith('.exr'):
            file_path = os.path.join(self.working_directory, file_name)
            exr_files.append((file_name, file_path))
    
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