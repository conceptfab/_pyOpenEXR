"""
Moduł do przetwarzania obrazów EXR.
"""

import sys
import logging
import numpy as np
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Klasa odpowiedzialna za przetwarzanie obrazów EXR.
    """
    
    @staticmethod
    def prepare_preview_data(part_data, item_type, layer_name=None, channel_name=None):
        """
        Przygotowuje dane do podglądu na podstawie wybranego elementu.
        
        Args:
            part_data (dict): Dane części pliku EXR
            item_type (str): Typ elementu ('layer' lub 'channel')
            layer_name (str, optional): Nazwa warstwy
            channel_name (str, optional): Nazwa kanału
            
        Returns:
            numpy.ndarray: Dane do wyświetlenia
        """
        channels = part_data.get("channels", {})
        layers = part_data.get("layers", {})
        
        if item_type == "layer" and layer_name:
            return ImageProcessor._prepare_layer_preview(channels, layers, layer_name)
        elif item_type == "channel" and channel_name:
            return ImageProcessor._prepare_channel_preview(channels, channel_name)
        
        return None
    
    @staticmethod
    def _prepare_layer_preview(channels, layers, layer_name):
        """Przygotowuje podgląd warstwy."""
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
                return np.stack([r, g, b, a], axis=-1)
        
        # Jeśli nie ma RGB, pokaż pierwszy kanał z warstwy
        if layer_channels:
            ch_name = str(layer_channels[0])
            print(f"[INFO] Brak kanałów RGB, używam pierwszego kanału: {ch_name}", file=sys.stderr)
            return channels.get(ch_name)
        
        return None
    
    @staticmethod
    def _prepare_channel_preview(channels, channel_name):
        """Przygotowuje podgląd pojedynczego kanału."""
        print(f"[INFO] Przygotowanie podglądu kanału: {channel_name}", file=sys.stderr)
        return channels.get(channel_name)
    
    @staticmethod
    def prepare_rgb_preview(part_data, layer_name):
        """
        Przygotowuje podgląd RGB dla określonej warstwy - prosta, niezawodna implementacja.
        
        Args:
            part_data (dict): Dane części pliku EXR
            layer_name (str): Nazwa warstwy
            
        Returns:
            numpy.ndarray: Dane RGB do wyświetlenia (już skonwertowane do sRGB)
        """
        print(f"[INFO] Przygotowanie podglądu RGB dla warstwy: {layer_name}", file=sys.stderr)
        
        # Użyj już załadowanych danych z part_data zamiast ponownego otwierania pliku
        channels = part_data.get("channels", {})
        layers = part_data.get("layers", {})
        
        # Znajdź kanały RGB w warstwie
        layer_channels = layers.get(layer_name, [])
        r_ch = None
        g_ch = None  
        b_ch = None
        
        # Szukaj kanałów R, G, B
        for ch_name in layer_channels:
            ch_str = str(ch_name)
            ch_lower = ch_str.lower()
            if ch_str.endswith('.R') or ch_str == 'R' or ch_str.endswith('.red') or ch_lower.endswith('red'):
                r_ch = ch_str
            elif ch_str.endswith('.G') or ch_str == 'G' or ch_str.endswith('.green') or ch_lower.endswith('green'):
                g_ch = ch_str
            elif ch_str.endswith('.B') or ch_str == 'B' or ch_str.endswith('.blue') or ch_lower.endswith('blue'):
                b_ch = ch_str
        
        # Sprawdź czy mamy wszystkie kanały RGB
        if not (r_ch and g_ch and b_ch):
            print(f"[WARN] Brak kanałów RGB w warstwie {layer_name}. Dostępne kanały: {layer_channels}", file=sys.stderr)
            return None
            
        # Pobierz dane kanałów
        r_data = channels.get(r_ch)
        g_data = channels.get(g_ch)
        b_data = channels.get(b_ch)
        
        if r_data is None or g_data is None or b_data is None:
            print(f"[ERROR] Brak danych dla kanałów RGB", file=sys.stderr)
            return None
            
        print(f"[INFO] Znaleziono kanały RGB: {r_ch}, {g_ch}, {b_ch}", file=sys.stderr)
        print(f"[INFO] Rozmiar danych: R={r_data.shape}, G={g_data.shape}, B={b_data.shape}", file=sys.stderr)
        
        try:
            # Złóż kanały w obraz RGB (w przestrzeni liniowej)
            rgb_linear = np.stack([r_data, g_data, b_data], axis=-1).astype(np.float32)
            
            # Konwertuj z liniowej przestrzeni barw na sRGB
            rgb_srgb = ImageProcessor.linear_to_srgb(rgb_linear)
            
            print(f"[INFO] Pomyślnie utworzono podgląd RGB: {rgb_srgb.shape}", file=sys.stderr)
            return rgb_srgb
            
        except Exception as e:
            print(f"[ERROR] Błąd podczas tworzenia podglądu RGB: {e}", file=sys.stderr)
            return None
    
    @staticmethod
    def prepare_rgb_preview_linear(part_data, layer_name):
        """
        Przygotowuje oryginalne dane liniowe RGB (bez konwersji sRGB) dla ekspozycji/gammy.
        
        Args:
            part_data (dict): Dane części pliku EXR
            layer_name (str): Nazwa warstwy
            
        Returns:
            numpy.ndarray: Oryginalne dane RGB w przestrzeni liniowej (float32)
        """
        print(f"[INFO] Przygotowanie liniowych danych RGB dla warstwy: {layer_name}", file=sys.stderr)
        
        # Użyj już załadowanych danych z part_data
        channels = part_data.get("channels", {})
        layers = part_data.get("layers", {})
        
        # Znajdź kanały RGB w warstwie
        layer_channels = layers.get(layer_name, [])
        r_ch = None
        g_ch = None  
        b_ch = None
        
        # Szukaj kanałów R, G, B
        for ch_name in layer_channels:
            ch_str = str(ch_name)
            ch_lower = ch_str.lower()
            if ch_str.endswith('.R') or ch_str == 'R' or ch_str.endswith('.red') or ch_lower.endswith('red'):
                r_ch = ch_str
            elif ch_str.endswith('.G') or ch_str == 'G' or ch_str.endswith('.green') or ch_lower.endswith('green'):
                g_ch = ch_str
            elif ch_str.endswith('.B') or ch_str == 'B' or ch_str.endswith('.blue') or ch_lower.endswith('blue'):
                b_ch = ch_str
        
        # Sprawdź czy mamy wszystkie kanały RGB
        if not (r_ch and g_ch and b_ch):
            print(f"[WARN] Brak kanałów RGB w warstwie {layer_name}. Dostępne kanały: {layer_channels}", file=sys.stderr)
            return None
            
        # Pobierz dane kanałów
        r_data = channels.get(r_ch)
        g_data = channels.get(g_ch)
        b_data = channels.get(b_ch)
        
        if r_data is None or g_data is None or b_data is None:
            print(f"[ERROR] Brak danych dla kanałów RGB", file=sys.stderr)
            return None
            
        try:
            # Złóż kanały w obraz RGB (w przestrzeni liniowej) - BEZ konwersji sRGB
            rgb_linear = np.stack([r_data, g_data, b_data], axis=-1).astype(np.float32)
            
            print(f"[INFO] Pomyślnie utworzono liniowe dane RGB: {rgb_linear.shape}", file=sys.stderr)
            return rgb_linear
            
        except Exception as e:
            print(f"[ERROR] Błąd podczas tworzenia liniowych danych RGB: {e}", file=sys.stderr)
            return None
    
    @staticmethod
    def apply_color_correction(linear_image, exposure=0.0, gamma=2.2):
        """
        Stosuje korekcję ekspozycji i gammy do liniowych danych obrazu.

        Args:
            linear_image (np.array): Tablica NumPy z danymi float (liniowymi).
            exposure (float): Wartość ekspozycji w "przystankach" (stops).
            gamma (float): Wartość gammy.

        Returns:
            np.array: Tablica NumPy uint8 (0-255) gotowa do wyświetlenia.
        """
        if linear_image is None:
            return None
            
        # Zabezpiecz wejściowe dane przed ekstremalnymi wartościami
        safe_linear = np.clip(linear_image, 0.0, 100.0)
        safe_linear = np.nan_to_num(safe_linear, nan=0.0, posinf=100.0, neginf=0.0)
        
        # Krok 1: Zastosuj ekspozycję (na danych liniowych)
        with np.errstate(over='ignore', invalid='ignore'):
            exposed_image = safe_linear * (2.0 ** np.clip(exposure, -10.0, 10.0))

        # Krok 2: Zastosuj korekcję gamma
        # Zabezpieczenie, aby gamma nie była zerem ani ujemna
        safe_gamma = np.clip(gamma, 0.01, 10.0)
        with np.errstate(over='ignore', invalid='ignore'):
            gammad_image = np.power(np.clip(exposed_image, 0.0, 100.0), 1.0 / safe_gamma)
        
        # Krok 3: Przygotuj do wyświetlenia
        # Ogranicz wartości do zakresu [0, 1], aby uniknąć błędów przy konwersji
        clipped_image = np.clip(gammad_image, 0.0, 1.0)
        
        # Konwertuj na 8-bitowy format całkowitoliczbowy (0-255)
        final_image_uint8 = (clipped_image * 255).astype(np.uint8)

        return final_image_uint8
    
    @staticmethod
    def linear_to_srgb(linear_image):
        """
        Konwertuje obraz z liniowej przestrzeni barw na sRGB.
        To KLUCZOWY krok, aby obraz nie był za ciemny!
        """
        # Zabezpiecz przed ekstremalnymi wartościami HDR
        # Ogranicz do sensownego zakresu HDR (0 do 100)
        safe_linear = np.clip(linear_image, 0.0, 100.0)
        
        # Zastąp NaN i Inf zerami
        safe_linear = np.nan_to_num(safe_linear, nan=0.0, posinf=100.0, neginf=0.0)
        
        # Zastosuj formułę konwersji sRGB
        with np.errstate(over='ignore', invalid='ignore'):
            srgb_image = np.where(
                safe_linear <= 0.0031308,
                safe_linear * 12.92,
                1.055 * (safe_linear ** (1/2.4)) - 0.055
            )
        
        # Ogranicz wartości do zakresu [0, 1] i konwertuj na 8-bit
        srgb_image = np.clip(srgb_image, 0.0, 1.0)
        return (srgb_image * 255).astype(np.uint8)
    
    @staticmethod
    def apply_display_adjustments(image_data, brightness=0.0, contrast=1.0):
        """
        Stosuje korekty jasności i kontrastu do danych obrazu.
        
        Args:
            image_data (numpy.ndarray): Dane obrazu (8-bit lub float)
            brightness (float): Wartość jasności (-1.0 do 1.0)
            contrast (float): Wartość kontrastu (0.0 do 3.0)
            
        Returns:
            numpy.ndarray: Skorygowane dane obrazu (8-bit)
        """
        if image_data is None:
            return None
            
        # Kopiuj dane, aby nie modyfikować oryginału
        display_data = image_data.copy()
        
        # Sprawdź czy dane są już 8-bit (RGB) czy float (EXR)
        if display_data.dtype == np.uint8:
            # Konwertuj 8-bit na float [0,1] dla przetwarzania
            display_data = display_data.astype(np.float32) / 255.0
        
        # Prosta edycja podglądu (nie modyfikuje danych źródłowych EXR)
        display_data = (display_data - 0.5) * contrast + 0.5 + brightness
        
        # Prosty tone mapping i konwersja do 8-bit
        display_data = np.clip(display_data, 0.0, 1.0)
        return (display_data * 255).astype(np.uint8)
    
    @staticmethod
    def numpy_to_qimage(image_data):
        """
        Konwertuje numpy array na QImage.
        
        Args:
            image_data (numpy.ndarray): Dane obrazu 8-bit
            
        Returns:
            QImage: Obraz Qt
        """
        if image_data is None:
            return None
            
        height, width = image_data.shape[:2]

        if image_data.ndim == 3:  # Obraz kolorowy
            if image_data.shape[2] == 4:  # RGBA
                q_image_format = QImage.Format.Format_RGBA8888
                bytes_per_line = 4 * width
            elif image_data.shape[2] == 3:  # RGB
                q_image_format = QImage.Format.Format_RGB888
                bytes_per_line = 3 * width
            else:
                print(f"[WARN] Nieobsługiwany format kolorowy: {image_data.shape[2]} kanałów", file=sys.stderr)
                return None
        else:  # Skala szarości
            q_image_format = QImage.Format.Format_Grayscale8
            bytes_per_line = 1 * width

        # Tworzenie QImage z numpy array
        q_image = QImage(image_data.data, width, height, bytes_per_line, q_image_format)
        
        # QImage musi mieć własną kopię danych
        return q_image.copy()
    
    @staticmethod
    def create_scaled_pixmap(q_image, target_size):
        """
        Tworzy skalowany QPixmap z QImage.
        
        Args:
            q_image (QImage): Obraz źródłowy
            target_size (QSize): Docelowy rozmiar
            
        Returns:
            QPixmap: Skalowany obraz
        """
        if q_image is None:
            return None
            
        pixmap = QPixmap.fromImage(q_image)
        return pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ) 