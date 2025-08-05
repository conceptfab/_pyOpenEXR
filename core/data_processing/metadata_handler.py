"""
Moduł do obsługi metadanych plików EXR.
"""

import sys
import logging
import numpy as np
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt6.QtGui import QColor, QFont

logger = logging.getLogger(__name__)


class MetadataHandler:
    """
    Klasa odpowiedzialna za obsługę metadanych plików EXR.
    """
    
    @staticmethod
    def populate_metadata_table(table_widget, header, channels_data=None):
        """
        Wypełnia tabelę metadanymi z nagłówka pliku EXR.
        
        Args:
            table_widget (QTableWidget): Widget tabeli do wypełnienia
            header (dict): Nagłówek pliku EXR
            channels_data (dict): Dane kanałów do obliczenia statystyk
        """
        table_widget.setRowCount(0)
        
        # Kategorie metadanych z kolorami
        categories = {
            "📐 Podstawowe informacje": {
                "dataWindow": "Okno danych",
                "displayWindow": "Okno wyświetlania", 
                "channels": "Kanały",
                "pixelAspectRatio": "Proporcje pikseli",
                "lineOrder": "Kolejność linii",
                "compression": "Kompresja"
            },
            "🎨 Metadane kolorów": {
                "chromaticities": "Chromatyczność",
                "whiteLuminance": "Luminancja bieli",
                "adoptedNeutral": "Neutralny punkt",
                "renderingTransform": "Transformacja renderowania",
                "lookModTransform": "Transformacja look modification",
                "acesImageContainerFlag": "Flaga kontenera ACES"
            },
            "⚙️ Metadane techniczne": {
                "worldToCamera": "Transformacja świat-kamera",
                "worldToNDC": "Transformacja świat-NDC", 
                "deepImageState": "Stan obrazu głębokiego",
                "dwaCompressionLevel": "Poziom kompresji DWA",
                "tiles": "Informacje o tiling",
                "chunkCount": "Liczba chunków",
                "tiledesc": "Opis tiling"
            },
            "🏷️ Metadane użytkownika": {
                "software": "Oprogramowanie",
                "comment": "Komentarz",
                "capDate": "Data utworzenia",
                "utcOffset": "Offset UTC",
                "owner": "Właściciel",
                "longName": "Długa nazwa",
                "nonImageData": "Dane nieobrazowe"
            }
        }
        
        row = 0
        
        # Dodaj metadane pogrupowane według kategorii
        for category_name, category_fields in categories.items():
            # Sprawdź czy kategoria ma jakieś dane
            category_has_data = any(field_name in header for field_name in category_fields.keys())
            
            if category_has_data:
                # Dodaj nagłówek kategorii tylko jeśli ma dane
                table_widget.insertRow(row)
                category_item = QTableWidgetItem(category_name)
                category_item.setBackground(QColor(50, 50, 50))  # Ciemne tło
                category_item.setForeground(QColor(255, 255, 255))  # Biały tekst
                category_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                table_widget.setItem(row, 0, category_item)
                
                # Pusty item z tym samym tłem
                empty_item = QTableWidgetItem("")
                empty_item.setBackground(QColor(50, 50, 50))
                table_widget.setItem(row, 1, empty_item)
                row += 1
                
                # Dodaj pola z tej kategorii
                for field_name, field_description in category_fields.items():
                    if field_name in header:
                        value = header[field_name]
                        formatted_value = MetadataHandler._format_metadata_value(value, field_name)
                        
                        table_widget.insertRow(row)
                        key_item = QTableWidgetItem(f"  {field_description}")
                        key_item.setBackground(QColor(35, 35, 35))  # Ciemne tło dla kluczy
                        key_item.setForeground(QColor(220, 220, 220))  # Jasny tekst
                        table_widget.setItem(row, 0, key_item)
                        
                        value_item = QTableWidgetItem(formatted_value)
                        value_item.setBackground(QColor(35, 35, 35))  # Ciemne tło dla wartości
                        value_item.setForeground(QColor(200, 200, 200))  # Jasny tekst
                        table_widget.setItem(row, 1, value_item)
                        row += 1
        
        # Dodaj pozostałe metadane (customowe)
        custom_metadata = {k: v for k, v in header.items() 
                          if k not in [field for fields in categories.values() for field in fields]}
        
        if custom_metadata:
            # Nagłówek dla customowych metadanych
            table_widget.insertRow(row)
            custom_header = QTableWidgetItem("🔧 Metadane niestandardowe")
            custom_header.setBackground(QColor(60, 40, 40))  # Ciemne czerwone tło
            custom_header.setForeground(QColor(255, 255, 255))  # Biały tekst
            custom_header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            table_widget.setItem(row, 0, custom_header)
            
            # Pusty item z tym samym tłem
            empty_item = QTableWidgetItem("")
            empty_item.setBackground(QColor(60, 40, 40))
            table_widget.setItem(row, 1, empty_item)
            row += 1
            
            for key, value in custom_metadata.items():
                formatted_value = MetadataHandler._format_metadata_value(value, key)
                table_widget.insertRow(row)
                key_item = QTableWidgetItem(f"  {key}")
                key_item.setBackground(QColor(35, 35, 35))  # Ciemne tło dla kluczy
                key_item.setForeground(QColor(220, 220, 220))  # Jasny tekst
                table_widget.setItem(row, 0, key_item)
                
                value_item = QTableWidgetItem(formatted_value)
                value_item.setBackground(QColor(35, 35, 35))  # Ciemne tło dla wartości
                value_item.setForeground(QColor(200, 200, 200))  # Jasny tekst
                table_widget.setItem(row, 1, value_item)
                row += 1
        
        # Dodaj statystyki obrazu jeśli dostępne
        if channels_data:
            MetadataHandler._add_image_statistics(table_widget, channels_data, row)
            # Dodaj szczegóły kanałów
            row = MetadataHandler.add_channel_details(table_widget, header, channels_data, row)
    
    @staticmethod
    def _format_metadata_value(value, field_name):
        """Formatuje wartość metadanych dla wyświetlenia."""
        if value is None:
            return "Brak"
        
        # Specjalne formatowanie dla różnych typów
        if field_name == "dataWindow":
            try:
                return f"({value.min.x}, {value.min.y}) - ({value.max.x}, {value.max.y})"
            except:
                return str(value)
        
        elif field_name == "displayWindow":
            try:
                return f"({value.min.x}, {value.min.y}) - ({value.max.x}, {value.max.y})"
            except:
                return str(value)
        
        elif field_name == "channels":
            try:
                channel_names = list(value.keys())
                return f"{len(channel_names)} kanałów: {', '.join(channel_names[:5])}{'...' if len(channel_names) > 5 else ''}"
            except:
                return str(value)
        
        elif field_name == "chromaticities":
            try:
                return f"R({value.red.x:.3f}, {value.red.y:.3f}) G({value.green.x:.3f}, {value.green.y:.3f}) B({value.blue.x:.3f}, {value.blue.y:.3f}) W({value.white.x:.3f}, {value.white.y:.3f})"
            except:
                return str(value)
        
        elif field_name == "worldToCamera":
            try:
                return f"Macierz 4x4: {value.v[0][0]:.3f}, {value.v[0][1]:.3f}, ..."
            except:
                return str(value)
        
        elif field_name == "compression":
            try:
                # Sprawdź czy to obiekt Compression
                if hasattr(value, 'v'):
                    compression_value = value.v
                else:
                    compression_value = value
                
                compression_names = {
                    0: "NO_COMPRESSION",
                    1: "RLE_COMPRESSION", 
                    2: "ZIPS_COMPRESSION",
                    3: "ZIP_COMPRESSION",
                    4: "PIZ_COMPRESSION",
                    5: "PXR24_COMPRESSION",
                    6: "B44_COMPRESSION",
                    7: "B44A_COMPRESSION",
                    8: "DWAA_COMPRESSION",
                    9: "DWAB_COMPRESSION"
                }
                return compression_names.get(compression_value, f"UNKNOWN_{compression_value}")
            except:
                return str(value)
        
        elif field_name == "lineOrder":
            try:
                # Sprawdź czy to obiekt LineOrder
                if hasattr(value, 'v'):
                    line_order_value = value.v
                else:
                    line_order_value = value
                
                line_order_names = {
                    0: "INCREASING_Y",
                    1: "DECREASING_Y", 
                    2: "RANDOM_Y"
                }
                return line_order_names.get(line_order_value, f"UNKNOWN_{line_order_value}")
            except:
                return str(value)
        
        elif isinstance(value, (list, tuple)):
            if len(value) <= 10:
                return str(value)
            else:
                return f"[{', '.join(map(str, value[:5]))}, ... ({len(value)} elementów)]"
        
        elif isinstance(value, dict):
            if len(value) <= 5:
                return str(value)
            else:
                keys = list(value.keys())[:3]
                return f"{{{', '.join(keys)}}}, ... ({len(value)} kluczy)"
        
        else:
            return str(value)
    
    @staticmethod
    def _add_image_statistics(table_widget, channels_data, start_row):
        """Dodaje statystyki obrazu do tabeli."""
        if not channels_data:
            return
        
        # Nagłówek statystyk
        table_widget.insertRow(start_row)
        stats_header = QTableWidgetItem("📊 Statystyki obrazu")
        stats_header.setBackground(QColor(40, 60, 40))  # Ciemne zielone tło
        stats_header.setForeground(QColor(255, 255, 255))  # Biały tekst
        stats_header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        table_widget.setItem(start_row, 0, stats_header)
        
        # Pusty item z tym samym tłem
        empty_item = QTableWidgetItem("")
        empty_item.setBackground(QColor(40, 60, 40))
        table_widget.setItem(start_row, 1, empty_item)
        start_row += 1
        
        # Statystyki dla każdego kanału
        for channel_name, channel_data in channels_data.items():
            if not isinstance(channel_data, np.ndarray):
                continue
            
            try:
                # Podstawowe statystyki
                min_val = np.min(channel_data)
                max_val = np.max(channel_data)
                mean_val = np.mean(channel_data)
                std_val = np.std(channel_data)
                
                # Percentyle
                p1 = np.percentile(channel_data, 1)
                p5 = np.percentile(channel_data, 5)
                p25 = np.percentile(channel_data, 25)
                p50 = np.percentile(channel_data, 50)  # mediana
                p75 = np.percentile(channel_data, 75)
                p95 = np.percentile(channel_data, 95)
                p99 = np.percentile(channel_data, 99)
                
                # Dodaj statystyki do tabeli
                stats_items = [
                    (f"  {channel_name} - Min/Max", f"{min_val:.6f} / {max_val:.6f}"),
                    (f"  {channel_name} - Średnia/Std", f"{mean_val:.6f} / {std_val:.6f}"),
                    (f"  {channel_name} - Mediana", f"{p50:.6f}"),
                    (f"  {channel_name} - Percentyle (1%,5%,25%,75%,95%,99%)", 
                     f"{p1:.3f}, {p5:.3f}, {p25:.3f}, {p75:.3f}, {p95:.3f}, {p99:.3f}")
                ]
                
                for label, value in stats_items:
                    table_widget.insertRow(start_row)
                    key_item = QTableWidgetItem(label)
                    key_item.setBackground(QColor(35, 35, 35))  # Ciemne tło dla kluczy
                    key_item.setForeground(QColor(220, 220, 220))  # Jasny tekst
                    table_widget.setItem(start_row, 0, key_item)
                    
                    value_item = QTableWidgetItem(value)
                    value_item.setBackground(QColor(35, 35, 35))  # Ciemne tło dla wartości
                    value_item.setForeground(QColor(200, 200, 200))  # Jasny tekst
                    table_widget.setItem(start_row, 1, value_item)
                    start_row += 1
                    
            except Exception as e:
                logger.warning(f"Błąd przy obliczaniu statystyk dla kanału {channel_name}: {e}")
                continue
    
    @staticmethod
    def add_channel_details(table_widget, header, channels_data, start_row):
        """Dodaje szczegółowe informacje o kanałach."""
        if not channels_data:
            return start_row
        
        # Nagłówek informacji o kanałach
        table_widget.insertRow(start_row)
        channel_header = QTableWidgetItem("🔍 Szczegóły kanałów")
        channel_header.setBackground(QColor(60, 60, 40))  # Ciemne żółte tło
        channel_header.setForeground(QColor(255, 255, 255))  # Biały tekst
        channel_header.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        table_widget.setItem(start_row, 0, channel_header)
        
        # Pusty item z tym samym tłem
        empty_item = QTableWidgetItem("")
        empty_item.setBackground(QColor(60, 60, 40))
        table_widget.setItem(start_row, 1, empty_item)
        start_row += 1
        
        # Pobierz informacje o kanałach z nagłówka
        header_channels = header.get("channels", {})
        
        for channel_name, channel_data in channels_data.items():
            if not isinstance(channel_data, np.ndarray):
                continue
            
            try:
                # Informacje o typie danych
                dtype = channel_data.dtype
                shape = channel_data.shape
                
                # Informacje z nagłówka
                channel_info = header_channels.get(channel_name, None)
                pixel_type = "Nieznany"
                if channel_info:
                    try:
                        if hasattr(channel_info, 'type'):
                            pt = channel_info.type
                            if pt == 0:  # UINT
                                pixel_type = "UINT (32-bit integer)"
                            elif pt == 1:  # HALF
                                pixel_type = "HALF (16-bit float)"
                            elif pt == 2:  # FLOAT
                                pixel_type = "FLOAT (32-bit float)"
                            else:
                                pixel_type = f"UNKNOWN_{pt}"
                    except:
                        pixel_type = str(channel_info)
                
                # Dodaj informacje o kanale
                channel_items = [
                    (f"  {channel_name} - Typ piksela", pixel_type),
                    (f"  {channel_name} - Typ danych NumPy", str(dtype)),
                    (f"  {channel_name} - Rozmiar", f"{shape[1]}x{shape[0]} pikseli"),
                    (f"  {channel_name} - Rozmiar w pamięci", f"{channel_data.nbytes / 1024 / 1024:.2f} MB")
                ]
                
                for label, value in channel_items:
                    table_widget.insertRow(start_row)
                    key_item = QTableWidgetItem(label)
                    key_item.setBackground(QColor(35, 35, 35))  # Ciemne tło dla kluczy
                    key_item.setForeground(QColor(220, 220, 220))  # Jasny tekst
                    table_widget.setItem(start_row, 0, key_item)
                    
                    value_item = QTableWidgetItem(value)
                    value_item.setBackground(QColor(35, 35, 35))  # Ciemne tło dla wartości
                    value_item.setForeground(QColor(200, 200, 200))  # Jasny tekst
                    table_widget.setItem(start_row, 1, value_item)
                    start_row += 1
                    
            except Exception as e:
                logger.warning(f"Błąd przy analizie kanału {channel_name}: {e}")
                continue
        
        return start_row
    
    @staticmethod
    def get_metadata_from_table(table_widget):
        """
        Pobiera metadane z tabeli.
        
        Args:
            table_widget (QTableWidget): Widget tabeli
            
        Returns:
            dict: Słownik metadanych
        """
        metadata = {}
        for row in range(table_widget.rowCount()):
            key_item = table_widget.item(row, 0)
            value_item = table_widget.item(row, 1)
            if key_item and value_item:
                key = key_item.text().strip()
                # Pomiń nagłówki kategorii i wcięcia
                if not key.startswith("📐") and not key.startswith("🎨") and not key.startswith("⚙️") and not key.startswith("🏷️") and not key.startswith("🔧") and not key.startswith("📊"):
                    if key.startswith("  "):
                        key = key[2:]  # Usuń wcięcie
                    metadata[key] = value_item.text()
        return metadata
    
    @staticmethod
    def update_header_with_metadata(header, metadata):
        """
        Aktualizuje nagłówek metadanymi.
        
        Args:
            header (dict): Oryginalny nagłówek
            metadata (dict): Nowe metadane
            
        Returns:
            dict: Zaktualizowany nagłówek
        """
        updated_header = header.copy()
        for key, value in metadata.items():
            updated_header[key] = value
        return updated_header 