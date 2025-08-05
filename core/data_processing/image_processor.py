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
    def apply_display_adjustments(image_data, brightness=0.0, contrast=1.0):
        """
        Stosuje korekty jasności i kontrastu do danych obrazu.
        
        Args:
            image_data (numpy.ndarray): Dane obrazu
            brightness (float): Wartość jasności (-1.0 do 1.0)
            contrast (float): Wartość kontrastu (0.0 do 3.0)
            
        Returns:
            numpy.ndarray: Skorygowane dane obrazu
        """
        if image_data is None:
            return None
            
        # Kopiuj dane, aby nie modyfikować oryginału
        display_data = image_data.copy()
        
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

        if image_data.ndim == 3:  # Obraz kolorowy (RGBA)
            q_image_format = QImage.Format.Format_RGBA8888
            bytes_per_line = 4 * width
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