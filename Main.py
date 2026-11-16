# -*- coding: utf-8 -*-
"""
main.py - Generación de animación
=================================
Orquesta las tres etapas (más un epílogo de texto) en la consola de Windows.

Uso:
    python main.py                  # animación normal
    python main.py --velocidad 2    # el doble de rápido
    python main.py --sin-texto      # sin el "para ti" final
"""

import argparse
import os
import shutil
import sys
import time

import colorama

import animaciones as an

# Retardo entre fotogramas (segundos) de cada etapa, a velocidad 1.0
RETARDO_MARIPOSA = 0.035
RETARDO_TALLOS = 0.045
RETARDO_FLORES = 0.05
RETARDO_TEXTO = 0.18
PAUSA_ENTRE_ETAPAS = 0.8
PAUSA_FINAL = 4.0


def reproducir(generador, retardo, cols, filas):
    """Dibuja cada fotograma sobre el anterior (cursor al inicio, sin parpadeo)."""
    for frame in generador:
        # \033[H = cursor a la esquina superior izquierda; se reescribe todo el cuadro
        sys.stdout.write("\033[H" + an.renderizar(frame, cols, filas))
        sys.stdout.flush()
        time.sleep(retardo)


def main():
    parser = argparse.ArgumentParser(description="Generación de animación (ASCII en terminal)")
    parser.add_argument("--velocidad", type=float, default=1.0, help="multiplicador de velocidad (def. 1.0)")
    parser.add_argument("--sin-texto", action="store_true", help="omite el texto final")
    args = parser.parse_args()
    vel = max(args.velocidad, 0.05)

    # Activa el procesamiento de secuencias ANSI en CMD/PowerShell de Windows 10+
    os.system("")
    colorama.init()

    # Tamaño de la terminal -> tamaño del lienzo (ver docstring de animaciones.py)
    cols, filas = shutil.get_terminal_size((100, 40))
    alto = an.dimensionar(cols, filas)
    lienzo = an.Lienzo(alto)
    if filas - 2 < an.ALTO_MIN or cols < int(an.ALTO_MIN * an.ASPECTO) + 1:
        print("Aviso: la terminal es muy pequeña; maximiza la ventana para ver la animación completa.")
        time.sleep(2)

    fondo = an.Lienzo(alto)       # acumula lo ya dibujado entre etapas
    try:
        sys.stdout.write("\033[2J\033[?25l")   # limpiar pantalla + ocultar cursor
        reproducir(an.etapa_mariposa(lienzo, fondo), RETARDO_MARIPOSA / vel, cols, filas)
        time.sleep(PAUSA_ENTRE_ETAPAS / vel)
        reproducir(an.etapa_tallos(lienzo, fondo), RETARDO_TALLOS / vel, cols, filas)
        time.sleep(PAUSA_ENTRE_ETAPAS / vel)
        reproducir(an.etapa_flores(lienzo, fondo), RETARDO_FLORES / vel, cols, filas)
        if not args.sin_texto:
            time.sleep(0.4 / vel)
            reproducir(an.etapa_texto(lienzo, fondo), RETARDO_TEXTO / vel, cols, filas)
        time.sleep(PAUSA_FINAL / vel)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[0m\033[?25h\n")   # restaurar color y cursor
        sys.stdout.flush()
        colorama.deinit()


if __name__ == "__main__":
    main()
      
