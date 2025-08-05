Stwórz aplikację desktopową w języku Python z graficznym interfejsem użytkownika (GUI) opartym na PyQt6, której celem jest edycja i eksploracja plików OpenEXR. Załaduj plik EXR i wyświetl listę wszystkich dostępnych warstw (layers), kanałów (channels), partów (parts) oraz innych możliwych do edycji elementów (np. metadanych, podglądu różnych passów renderu).

Funkcjonalności:

Okno wyboru pliku .exr do otwarcia.

Panel nawigacyjny z listą wszystkich wykrytych warstw/partów i kanałów (np. Beauty, Z, Normals; z podziałem na R, G, B, A, itp.).

Podgląd każdej warstwy/kanału w formie obrazu (może być uproszczona konwersja HDR do 8-bitowego poglądu).

Możliwość wybrania i edycji wartości pojedynczego kanału (np. przez krzywe lub prostą operację na macierzy).

Obsługa odczytu i zapisu plików EXR; możliwość edycji i nadpisania lub zapisania pod nową nazwą.

Wyświetlanie i możliwość edycji metadanych pliku (np. rozdzielczość, kompresja, niestandardowe atrybuty).

GUI z podziałem na listę warstw, panel edycji oraz podgląd.

Zastosuj bibliotekę OpenEXR lub openexr-python do obsługi plików oraz numpy do przetwarzania danych obrazu.

Dodatkowo:

Wszystkie operacje muszą być możliwe do wykonania graficznie (bez użycia linii komend).

Aplikacja powinna automatycznie wykrywać strukturę multi-part/multilayer pliku EXR.

Każda zmiana widoczna natychmiast w podglądzie.

Stabilność dla dużych plików (asynchroniczny odczyt/zapis).

Prompt można dostosować do konkretnego modelu (np. Copilot, ChatGPT, Claude) lub przekazać programiście. Wszystkie najważniejsze szczegóły dotyczące obsługi warstw, kanałów, elementów edytowalnych i specyfiki EXR są już w nim zawarte.



https://pypi.org/project/kriptomatte/


Główne Opcje dla Rusta
1. Crate exr (Zalecane)
Jest to wysokopoziomowa, bezpieczna i "idiomatyczna" biblioteka w Ruście. Co to oznacza w praktyce:
Bezpieczeństwo Pamięci: Napisana w dużej mierze w czystym Ruście, co gwarantuje bezpieczeństwo pamięci i unikanie błędów typowych dla C++.
Proste API: Oferuje łatwy w użyciu interfejs do odczytu i zapisu plików EXR, w tym metadanych, warstw i kanałów.
Brak Zależności Systemowych: Nie wymaga instalowania biblioteki C++ OpenEXR na Twoim systemie. Wszystko jest zarządzane przez menedżera pakietów Cargo, co ogromnie upraszcza budowanie projektu i jego przenośność.
Wydajność: Jest zoptymalizowana pod kątem wydajności i dobrze wykorzystuje współbieżność Rusta.