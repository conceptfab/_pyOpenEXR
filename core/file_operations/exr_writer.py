"""
Moduł do zapisu plików OpenEXR.
"""

import sys
import logging
import OpenEXR

logger = logging.getLogger(__name__)


class EXRWriter:
    """
    Klasa odpowiedzialna za zapis plików OpenEXR.
    """
    
    @staticmethod
    def save_exr_file(filepath, data):
        """
        Zapisuje dane do pliku EXR.
        
        Args:
            filepath (str): Ścieżka do pliku docelowego
            data (dict): Struktura danych do zapisu
        """
        print(f"[INFO] Rozpoczęcie zapisu pliku EXR: {filepath}", file=sys.stderr)
        
        headers = []
        parts_data = []

        for part_info in data["parts"]:
            header = EXRWriter._create_header(part_info)
            channels_to_write = EXRWriter._prepare_channels_data(part_info)
            
            headers.append(header)
            parts_data.append(channels_to_write)

        try:
            exr_output = OpenEXR.MultiPartOutputFile(filepath, headers)
            exr_output.writePixels(parts_data)
            print(f"[INFO] Plik został pomyślnie zapisany: {filepath}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Błąd podczas zapisu pliku: {e}", file=sys.stderr)
            raise
    
    @staticmethod
    def _create_header(part_info):
        """Tworzy nagłówek dla części pliku EXR."""
        size = part_info["size"]
        header = OpenEXR.Header(size[0], size[1])
        
        # Kopiuj/zaktualizuj metadane z oryginalnego nagłówka
        original_header = part_info["header"]
        for key, value in original_header.items():
            header[key] = value
            
        return header
    
    @staticmethod
    def _prepare_channels_data(part_info):
        """Przygotowuje dane kanałów do zapisu."""
        channels_to_write = {}
        for ch_name, np_array in part_info["channels"].items():
            channels_to_write[ch_name] = np_array.tobytes()
        return channels_to_write 