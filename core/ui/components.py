"""
Moduł zawierający komponenty interfejsu użytkownika.
"""

import sys
import logging
import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenuBar,
    QSlider,
    QSplitter,
    QTableWidget,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class TreeNavigator:
    """
    Klasa odpowiedzialna za nawigację drzewa plików EXR.
    """
    
    @staticmethod
    def create_tree_widget():
        """Tworzy widget drzewa nawigacji."""
        tree_widget = QTreeWidget()
        tree_widget.setHeaderLabels(["Element", "Typ"])
        tree_widget.setColumnWidth(0, 200)
        return tree_widget
    
    @staticmethod
    def populate_tree(tree_widget, exr_data):
        """
        Wypełnia drzewo danymi z pliku EXR.
        
        Args:
            tree_widget (QTreeWidget): Widget drzewa
            exr_data (dict): Dane pliku EXR
        """
        print("[INFO] Aktualizacja drzewa nawigacji", file=sys.stderr)
        tree_widget.clear()
        if not exr_data:
            print("[WARN] Brak danych EXR do wyświetlenia w drzewie", file=sys.stderr)
            return

        filepath = exr_data.get("filepath", "")
        file_item = QTreeWidgetItem(
            tree_widget, [os.path.basename(filepath), "Plik"]
        )

        parts_iter = exr_data.get("parts", [])
        for i, part_data in enumerate(parts_iter):
            part_name = part_data.get("name", "default")
            layers = part_data.get("layers", {})
            print(f"[DEBUG] Dodawanie części do drzewa: {part_name}", file=sys.stderr)

            part_item = QTreeWidgetItem(file_item, [part_name, "Part"])
            part_item.setData(0, Qt.ItemDataRole.UserRole, ("part", i))

            for layer_name, channel_list in layers.items():
                print(f"[DEBUG] Dodawanie warstwy do drzewa: {layer_name} ({len(channel_list)} kanałów)", file=sys.stderr)
                layer_item = QTreeWidgetItem(part_item, [layer_name, "Warstwa"])
                layer_item.setData(0, Qt.ItemDataRole.UserRole, ("layer", i, layer_name))

                for ch_name in channel_list:
                    ch_name_s = str(ch_name)
                    channel_item = QTreeWidgetItem(layer_item, [ch_name_s, "Kanał"])
                    channel_item.setData(0, Qt.ItemDataRole.UserRole, ("channel", i, ch_name_s))

        tree_widget.expandAll()
        print("[INFO] Drzewo nawigacji zostało zaktualizowane", file=sys.stderr)


class ImagePreview:
    """
    Klasa odpowiedzialna za podgląd obrazu.
    """
    
    @staticmethod
    def create_preview_widget():
        """Tworzy widget podglądu obrazu."""
        image_preview = QLabel("Otwórz plik .exr, aby rozpocząć")
        image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_preview.setMinimumSize(400, 300)
        return image_preview


class ControlPanel:
    """
    Klasa odpowiedzialna za panel kontrolny.
    """
    
    @staticmethod
    def create_control_widget():
        """Tworzy widget z kontrolkami edycji."""
        edit_widget = QWidget()
        edit_layout = QFormLayout(edit_widget)
        
        brightness_slider = QSlider(Qt.Orientation.Horizontal)
        brightness_slider.setRange(-100, 100)
        brightness_slider.setValue(0)

        contrast_slider = QSlider(Qt.Orientation.Horizontal)
        contrast_slider.setRange(0, 300)  # 100 = 1.0
        contrast_slider.setValue(100)

        edit_layout.addRow("Jasność:", brightness_slider)
        edit_layout.addRow("Kontrast:", contrast_slider)
        
        return edit_widget, brightness_slider, contrast_slider


class MetadataPanel:
    """
    Klasa odpowiedzialna za panel metadanych.
    """
    
    @staticmethod
    def create_metadata_widget():
        """Tworzy widget tabeli metadanych."""
        metadata_table = QTableWidget()
        metadata_table.setColumnCount(2)
        metadata_table.setHorizontalHeaderLabels(["Atrybut", "Wartość"])
        metadata_table.setColumnWidth(0, 150)
        metadata_table.horizontalHeader().setStretchLastSection(True)
        return metadata_table


class TabManager:
    """
    Klasa odpowiedzialna za zarządzanie zakładkami.
    """
    
    @staticmethod
    def create_tab_widget(control_widget, metadata_widget):
        """Tworzy widget z zakładkami."""
        tabs = QTabWidget()
        tabs.addTab(control_widget, "Kontrolki podglądu")
        tabs.addTab(metadata_widget, "Metadane")
        return tabs


class MenuManager:
    """
    Klasa odpowiedzialna za zarządzanie menu.
    """
    
    @staticmethod
    def create_menu_bar(main_window, open_callback, save_callback, save_as_callback):
        """
        Tworzy pasek menu.
        
        Args:
            main_window (QMainWindow): Główne okno aplikacji
            open_callback (callable): Funkcja wywoływana przy otwarciu pliku
            save_callback (callable): Funkcja wywoływana przy zapisie
            save_as_callback (callable): Funkcja wywoływana przy zapisie jako
        """
        menu_bar = main_window.menuBar()
        file_menu = menu_bar.addMenu("&Plik")

        open_action = QAction("&Otwórz...", main_window)
        open_action.triggered.connect(open_callback)
        file_menu.addAction(open_action)

        save_action = QAction("&Zapisz", main_window)
        save_action.triggered.connect(save_callback)
        file_menu.addAction(save_action)

        save_as_action = QAction("Zapisz &jako...", main_window)
        save_as_action.triggered.connect(save_as_callback)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("&Wyjdź", main_window)
        exit_action.triggered.connect(main_window.close)
        file_menu.addAction(exit_action)
        
        return menu_bar 