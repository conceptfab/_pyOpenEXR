"""
Moduł zawierający komponenty interfejsu użytkownika.
"""

import sys
import logging
import os
import numpy as np
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
    QDoubleSpinBox,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QPushButton,
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import QSize, pyqtSignal, QObject

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
        
        # Jeśli jest tylko jedna część i nazywa się "default", pomiń poziom części
        single_part_default = (len(parts_iter) == 1 and 
                              parts_iter[0].get("name", "default") == "default")
        
        for i, part_data in enumerate(parts_iter):
            part_name = part_data.get("name", "default")
            layers = part_data.get("layers", {})
            print(f"[DEBUG] Dodawanie części do drzewa: {part_name}", file=sys.stderr)

            # Dla single-part z nazwą "default", dodaj warstwy bezpośrednio do pliku
            if single_part_default:
                parent_item = file_item
                print("[DEBUG] Single-part plik - pomijam poziom części", file=sys.stderr)
            else:
                # Multi-part lub nazwana część - pokaż poziom części
                part_item = QTreeWidgetItem(file_item, [part_name, "Part"])
                part_item.setData(0, Qt.ItemDataRole.UserRole, ("part", i))
                parent_item = part_item

            for layer_name, channel_list in layers.items():
                print(f"[DEBUG] Dodawanie warstwy do drzewa: {layer_name} ({len(channel_list)} kanałów)", file=sys.stderr)
                layer_item = QTreeWidgetItem(parent_item, [layer_name, "Warstwa"])
                layer_item.setData(0, Qt.ItemDataRole.UserRole, ("layer", i, layer_name))

                # Sprawdź czy warstwa ma sens dla podglądu RGB
                should_show = TreeNavigator._should_show_rgb_preview(part_data, layer_name)
                print(f"[DEBUG] Decyzja RGB podgląd dla {layer_name}: {should_show}", file=sys.stderr)
                if should_show:
                    rgb_item = QTreeWidgetItem(layer_item, ["RGB Podgląd", "RGB"])
                    rgb_item.setData(0, Qt.ItemDataRole.UserRole, ("rgb_preview", i, layer_name))

                for ch_name in channel_list:
                    ch_name_s = str(ch_name)
                    channel_item = QTreeWidgetItem(layer_item, [ch_name_s, "Kanał"])
                    channel_item.setData(0, Qt.ItemDataRole.UserRole, ("channel", i, ch_name_s))

        tree_widget.expandAll()
        print("[INFO] Drzewo nawigacji zostało zaktualizowane", file=sys.stderr)
    
    @staticmethod
    def _should_show_rgb_preview(part_data, layer_name):
        """
        Sprawdza czy warstwa powinna mieć opcję podglądu RGB.
        
        Args:
            part_data (dict): Dane części pliku EXR
            layer_name (str): Nazwa warstwy
            
        Returns:
            bool: True jeśli RGB podgląd ma sens
        """
        channels = part_data.get("channels", {})
        layers = part_data.get("layers", {})
        layer_channels = layers.get(layer_name, [])
        
        # Znajdź kanały RGB
        r_ch = None
        g_ch = None  
        b_ch = None
        
        for ch_name in layer_channels:
            ch_str = str(ch_name)
            ch_lower = ch_str.lower()
            if ch_str.endswith('.R') or ch_str == 'R' or ch_str.endswith('.red') or ch_lower.endswith('red'):
                r_ch = ch_str
            elif ch_str.endswith('.G') or ch_str == 'G' or ch_str.endswith('.green') or ch_lower.endswith('green'):
                g_ch = ch_str
            elif ch_str.endswith('.B') or ch_str == 'B' or ch_str.endswith('.blue') or ch_lower.endswith('blue'):
                b_ch = ch_str
        
        # Jeśli brak wszystkich kanałów RGB, nie pokazuj podglądu RGB
        if not (r_ch and g_ch and b_ch):
            print(f"[DEBUG] Warstwa {layer_name} - brak kanałów RGB: R={r_ch}, G={g_ch}, B={b_ch}, kanały={layer_channels}", file=sys.stderr)
            return False
        
        print(f"[DEBUG] Warstwa {layer_name} - znaleziono kanały RGB: R={r_ch}, G={g_ch}, B={b_ch}", file=sys.stderr)
            
        # Pobierz dane kanałów
        r_data = channels.get(r_ch)
        g_data = channels.get(g_ch)
        b_data = channels.get(b_ch)
        
        if r_data is None or g_data is None or b_data is None:
            return False
        
        try:
            # Sprawdź czy kanały są identyczne (np. alpha/ID pass)
            # Porównaj tylko fragmenty dla wydajności (10x10 pikseli z kilku miejsc)
            sample_size = min(10, min(r_data.shape))
            if sample_size < 2:
                # Za małe dane - pokaż RGB podgląd
                print(f"[DEBUG] Warstwa {layer_name} - za małe dane, pokazuję RGB podgląd", file=sys.stderr)
                return True
            
            # Sprawdź kilka próbek z różnych miejsc obrazu
            samples_match = 0
            total_samples = 0
            
            # Próbki z różnych miejsc: lewy górny, środek, prawy dolny
            positions = [
                (0, 0),  # lewy górny
                (r_data.shape[0]//2, r_data.shape[1]//2) if len(r_data.shape) > 1 else (r_data.shape[0]//2,),  # środek
                (r_data.shape[0]-sample_size, r_data.shape[1]-sample_size) if len(r_data.shape) > 1 else (r_data.shape[0]-sample_size,)  # prawy dolny
            ]
            
            for pos in positions:
                if len(r_data.shape) == 2:  # 2D array
                    if pos[0] + sample_size <= r_data.shape[0] and pos[1] + sample_size <= r_data.shape[1]:
                        r_sample = r_data[pos[0]:pos[0]+sample_size, pos[1]:pos[1]+sample_size]
                        g_sample = g_data[pos[0]:pos[0]+sample_size, pos[1]:pos[1]+sample_size]
                        b_sample = b_data[pos[0]:pos[0]+sample_size, pos[1]:pos[1]+sample_size]
                else:  # 1D array
                    if pos[0] + sample_size <= r_data.shape[0]:
                        r_sample = r_data[pos[0]:pos[0]+sample_size]
                        g_sample = g_data[pos[0]:pos[0]+sample_size]
                        b_sample = b_data[pos[0]:pos[0]+sample_size]
                    else:
                        continue
                
                total_samples += 1
                
                # Sprawdź czy próbka ma identyczne wartości
                if np.array_equal(r_sample, g_sample) and np.array_equal(g_sample, b_sample):
                    samples_match += 1
            
            # Jeśli wszystkie próbki są identyczne, to prawdopodobnie alpha/ID pass
            if total_samples > 0 and samples_match == total_samples:
                print(f"[DEBUG] Warstwa {layer_name} ma identyczne kanały RGB we wszystkich próbkach - pomijam RGB podgląd", file=sys.stderr)
                return False
            else:
                print(f"[DEBUG] Warstwa {layer_name} ma różne kanały RGB ({samples_match}/{total_samples} próbek identycznych) - dodaję RGB podgląd", file=sys.stderr)
                return True
                
        except Exception as e:
            print(f"[WARN] Błąd przy sprawdzaniu kanałów RGB dla {layer_name}: {e}", file=sys.stderr)
            # W przypadku błędu, domyślnie pokaż RGB podgląd
            return True


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
        
        # Jasność: -1.0 do 1.0
        brightness_container = QHBoxLayout()
        brightness_slider = QSlider(Qt.Orientation.Horizontal)
        brightness_slider.setRange(-100, 100)
        brightness_slider.setValue(0)
        brightness_spinbox = QDoubleSpinBox()
        brightness_spinbox.setRange(-1.0, 1.0)
        brightness_spinbox.setSingleStep(0.01)
        brightness_spinbox.setDecimals(2)
        brightness_spinbox.setValue(0.0)
        brightness_container.addWidget(brightness_slider)
        brightness_container.addWidget(brightness_spinbox)

        # Kontrast: 0.0 do 3.0
        contrast_container = QHBoxLayout()
        contrast_slider = QSlider(Qt.Orientation.Horizontal)
        contrast_slider.setRange(0, 300)  # 100 = 1.0
        contrast_slider.setValue(100)
        contrast_spinbox = QDoubleSpinBox()
        contrast_spinbox.setRange(0.0, 3.0)
        contrast_spinbox.setSingleStep(0.01)
        contrast_spinbox.setDecimals(2)
        contrast_spinbox.setValue(1.0)
        contrast_container.addWidget(contrast_slider)
        contrast_container.addWidget(contrast_spinbox)

        # Ekspozycja: -5.0 do +5.0 przystanków (stops)
        exposure_container = QHBoxLayout()
        exposure_slider = QSlider(Qt.Orientation.Horizontal)
        exposure_slider.setRange(-500, 500)  # -5.0 do +5.0 (dzielone przez 100)
        exposure_slider.setValue(0)
        exposure_spinbox = QDoubleSpinBox()
        exposure_spinbox.setRange(-5.0, 5.0)
        exposure_spinbox.setSingleStep(0.01)
        exposure_spinbox.setDecimals(2)
        exposure_spinbox.setValue(0.0)
        exposure_spinbox.setSuffix(" stops")
        exposure_container.addWidget(exposure_slider)
        exposure_container.addWidget(exposure_spinbox)

        # Gamma: 0.5 do 5.0
        gamma_container = QHBoxLayout()
        gamma_slider = QSlider(Qt.Orientation.Horizontal)
        gamma_slider.setRange(50, 500)  # 0.5 do 5.0 (dzielone przez 100)
        gamma_slider.setValue(220)  # domyślnie 2.2
        gamma_spinbox = QDoubleSpinBox()
        gamma_spinbox.setRange(0.5, 5.0)
        gamma_spinbox.setSingleStep(0.01)
        gamma_spinbox.setDecimals(2)
        gamma_spinbox.setValue(2.2)
        gamma_container.addWidget(gamma_slider)
        gamma_container.addWidget(gamma_spinbox)

        # Dodaj kontenery do layoutu
        edit_layout.addRow("Jasność:", brightness_container)
        edit_layout.addRow("Kontrast:", contrast_container)
        edit_layout.addRow("Ekspozycja:", exposure_container)
        edit_layout.addRow("Gamma:", gamma_container)
        
        # Synchronizuj suwaki z spinboxami
        ControlPanel._sync_slider_spinbox(brightness_slider, brightness_spinbox, 100.0)
        ControlPanel._sync_slider_spinbox(contrast_slider, contrast_spinbox, 100.0)
        ControlPanel._sync_slider_spinbox(exposure_slider, exposure_spinbox, 100.0)
        ControlPanel._sync_slider_spinbox(gamma_slider, gamma_spinbox, 100.0)
        
        return (edit_widget, brightness_slider, contrast_slider, exposure_slider, gamma_slider,
                brightness_spinbox, contrast_spinbox, exposure_spinbox, gamma_spinbox)
    
    @staticmethod
    def _sync_slider_spinbox(slider, spinbox, scale_factor):
        """
        Synchronizuje suwak ze spinboxem.
        
        Args:
            slider (QSlider): Suwak
            spinbox (QDoubleSpinBox): Spinbox
            scale_factor (float): Współczynnik skalowania (slider_value / scale_factor = spinbox_value)
        """
        # Synchronizuj slider -> spinbox
        def slider_changed(value):
            spinbox.blockSignals(True)
            spinbox.setValue(value / scale_factor)
            spinbox.blockSignals(False)
        
        # Synchronizuj spinbox -> slider
        def spinbox_changed(value):
            slider.blockSignals(True)
            slider.setValue(int(value * scale_factor))
            slider.blockSignals(False)
        
        slider.valueChanged.connect(slider_changed)
        spinbox.valueChanged.connect(spinbox_changed)


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
    def create_menu_bar(main_window, open_callback, save_callback, save_as_callback, open_folder_callback=None):
        """
        Tworzy pasek menu.
        
        Args:
            main_window (QMainWindow): Główne okno aplikacji
            open_callback (callable): Funkcja wywoływana przy otwarciu pliku
            save_callback (callable): Funkcja wywoływana przy zapisie
            save_as_callback (callable): Funkcja wywoływana przy zapisie jako
            open_folder_callback (callable, optional): Funkcja wywoływana przy wyborze folderu roboczego
        """
        menu_bar = main_window.menuBar()
        file_menu = menu_bar.addMenu("&Plik")

        open_action = QAction("&Otwórz...", main_window)
        open_action.triggered.connect(open_callback)
        file_menu.addAction(open_action)

        # Dodaj opcję wyboru folderu roboczego
        if open_folder_callback:
            folder_action = QAction("Wybierz &folder roboczy...", main_window)
            folder_action.triggered.connect(open_folder_callback)
            file_menu.addAction(folder_action)
            file_menu.addSeparator()

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


class FileBrowser:
    """
    Klasa odpowiedzialna za przeglądarkę plików EXR.
    """
    
    @staticmethod
    def create_file_browser_widget():
        """Tworzy widget przeglądarki plików."""
        browser_widget = QWidget()
        browser_layout = QVBoxLayout(browser_widget)
        browser_layout.setContentsMargins(0, 0, 0, 0)  # Usuń marginesy
        
        # Lista plików z miniaturami - na całą wysokość
        file_list = QListWidget()
        file_list.setViewMode(QListWidget.ViewMode.IconMode)
        file_list.setIconSize(QSize(100, 100))
        file_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        file_list.setSpacing(5)
        file_list.setUniformItemSizes(True)
        browser_layout.addWidget(file_list)
        
        # Przycisk wyboru folderu roboczego na dole
        folder_button = QPushButton("📁 Wybierz folder roboczy")
        folder_button.setStyleSheet("""
            QPushButton {
                padding: 8px;
                font-size: 12px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        folder_button.setFixedHeight(40)  # Stała wysokość
        browser_layout.addWidget(folder_button)
        
        # Etykieta informacyjna (opcjonalna, może być None)
        info_label = QLabel("")
        info_label.setStyleSheet("color: gray; font-style: italic; padding: 2px; font-size: 10px;")
        info_label.setWordWrap(True)
        info_label.setFixedHeight(20)  # Mniejsza wysokość
        info_label.hide()  # Domyślnie ukryta
        browser_layout.addWidget(info_label)
        
        return browser_widget, file_list, info_label, folder_button 