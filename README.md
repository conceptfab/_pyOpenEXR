# EXR Editor - Przeglądarka i Edytor Plików OpenEXR

Aplikacja do przeglądania i edycji plików OpenEXR napisana w Python z użyciem PyQt6.

## Struktura projektu

```
_pyOpenEXR/
├── pyOpenEXR.py              # Główny punkt wejścia aplikacji
├── core/                     # Główny pakiet aplikacji
│   ├── __init__.py
│   ├── file_operations/      # Operacje na plikach EXR
│   │   ├── __init__.py
│   │   ├── exr_reader.py     # Odczyt plików EXR
│   │   ├── exr_writer.py     # Zapis plików EXR
│   │   └── exr_loader.py     # Wątek operacji plikowych
│   ├── ui/                   # Komponenty interfejsu użytkownika
│   │   ├── __init__.py
│   │   ├── main_window.py    # Główne okno aplikacji
│   │   └── components.py     # Komponenty UI (drzewo, podgląd, kontrolki)
│   └── data_processing/      # Przetwarzanie danych
│       ├── __init__.py
│       ├── image_processor.py # Przetwarzanie obrazów
│       └── metadata_handler.py # Obsługa metadanych
└── README.md
```

## Moduły

### core.file_operations

- **EXRReader**: Odczyt plików OpenEXR z obsługą różnych wersji biblioteki
- **EXRWriter**: Zapis plików OpenEXR
- **FileOperationThread**: Asynchroniczne operacje plikowe w tle

### core.ui

- **EXREditor**: Główne okno aplikacji
- **TreeNavigator**: Nawigacja drzewa plików EXR
- **ImagePreview**: Podgląd obrazu
- **ControlPanel**: Panel kontrolny (jasność, kontrast)
- **MetadataPanel**: Panel metadanych
- **TabManager**: Zarządzanie zakładkami
- **MenuManager**: Zarządzanie menu

### core.data_processing

- **ImageProcessor**: Przetwarzanie obrazów (konwersja, korekty)
- **MetadataHandler**: Obsługa metadanych plików EXR

## Uruchomienie

```bash
python pyOpenEXR.py
```

## Funkcjonalności

- **Przeglądanie plików EXR**: Obsługa plików wieloczęściowych i pojedynczych
- **Nawigacja**: Drzewo z częściami, warstwami i kanałami
- **Podgląd obrazu**: Wyświetlanie warstw RGB i pojedynczych kanałów
- **Korekty podglądu**: Jasność i kontrast (nie modyfikuje danych źródłowych)
- **Metadane**: Przeglądanie i edycja metadanych pliku
- **Zapis**: Zapisywanie plików z zachowaniem struktury

## Wymagania

- Python 3.8+
- PyQt6
- OpenEXR
- numpy
- Imath

## Rozbudowa

Kod został przygotowany do rozbudowy poprzez:

- Modułową architekturę
- Separację logiki biznesowej od interfejsu
- Statyczne metody w klasach dla łatwego testowania
- Jasno zdefiniowane interfejsy między modułami
