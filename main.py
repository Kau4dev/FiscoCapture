"""
main.py — FiscoCapture
Ponto de entrada seguro com suporte a multiprocessamento congelado (PyInstaller).
"""

import multiprocessing
from interface import main

if __name__ == "__main__":
    # Garante suporte a multiprocessamento em executáveis compilados no Windows
    multiprocessing.freeze_support()
    main()
