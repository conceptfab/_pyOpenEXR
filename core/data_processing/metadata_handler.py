"""
Moduł do obsługi metadanych plików EXR.
"""

import sys
import logging
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem

logger = logging.getLogger(__name__)


class MetadataHandler:
    """
    Klasa odpowiedzialna za obsługę metadanych plików EXR.
    """
    
    @staticmethod
    def populate_metadata_table(table_widget, header):
        """
        Wypełnia tabelę metadanymi z nagłówka pliku EXR.
        
        Args:
            table_widget (QTableWidget): Widget tabeli do wypełnienia
            header (dict): Nagłówek pliku EXR
        """
        table_widget.setRowCount(0)
        for key, value in header.items():
            row_position = table_widget.rowCount()
            table_widget.insertRow(row_position)
            table_widget.setItem(row_position, 0, QTableWidgetItem(str(key)))
            table_widget.setItem(row_position, 1, QTableWidgetItem(str(value)))
    
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
                metadata[key_item.text()] = value_item.text()
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