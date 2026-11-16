# Generación de animación

Animación procedural en arte ASCII que se reproduce directamente en la consola
de Windows (PowerShell, CMD y Git Bash). Todo se calcula con fórmulas: no hay
imágenes ni fotogramas pregrabados.

## Las tres etapas

1. **Mariposa**: las alas simétricas se "imprimen" celda a celda con caracteres
   densos (`%#@`) en tonos verde esmeralda.
2. **Tallos y espirales**: seis tallos nacen del centro y crecen hacia arriba,
   ondulando y soltando zarcillos en espiral.
3. **Lirios**: en la punta de cada tallo se abre un lirio en capas de color
   (amarillo suave, blanco y estambres oscuros).

Al final aparece el texto "para ti" letra por letra.

## Requisitos

- Windows 10 o superior (también funciona en Linux/macOS).
- Python 3.8 o superior.
- Terminal con soporte de 256 colores (Windows Terminal, PowerShell 5+/7, CMD
  de Windows 10+ y Git Bash lo soportan).

## Instalación y ejecución

```bash
git clone https://github.com/<tu-usuario>/generacion-de-animacion.git
cd generacion-de-animacion
python -m venv .venv
.venv\Scripts\activate          # PowerShell / CMD   (Git Bash: source .venv/Scripts/activate)
pip install -r requirements.txt
python main.py
```

Opciones:

```bash
python main.py --velocidad 2    # el doble de rápido
python main.py --velocidad 0.5  # en cámara lenta
python main.py --sin-texto      # sin el "para ti" final
```

Pulsa `Ctrl+C` para salir; el cursor y los colores se restauran solos.

## Consejos

- **Maximiza la ventana** antes de ejecutar: el lienzo se adapta al tamaño de la
  terminal (hasta 44 filas) y cuanto más grande, más detalle tienen los lirios.
- Si ves secuencias raras como `←[38;5;...`, usa Windows Terminal o actualiza
  Windows; el CMD antiguo no interpreta colores ANSI.

## Estructura

```
.
├── main.py            # orquesta las etapas y los retardos (time.sleep)
├── animaciones.py     # lienzo, geometría procedural y generadores de fotogramas
├── requirements.txt   # colorama
└── README.md
```

## Cómo funciona (resumen)

- **Centrado**: `margen_izq = (columnas - ancho) // 2` y
  `margen_sup = (filas - alto) // 2`, con el tamaño leído de
  `shutil.get_terminal_size()`.
- **Celdas no cuadradas**: una celda mide ~1×2. Toda la geometría se define en
  un espacio isótropo (`X = (x+0.5-ancho/2)/D`, `Y = (y+0.5)*2/D`, `D = 2*alto`),
  así los círculos salen redondos y todo escala con el tamaño de la terminal.
- **Crecimiento fluido**: cada trazo avanza con `suave(t) = t²(3-2t)`
  (acelera y frena) y las espirales brotan cuando el tallo pasa por su punto de
  unión.
- **Pétalos**: en coordenadas polares con ancho angular
  `dmax(s) = ancho * sin(π·s^0.7)^0.8`, que da base estrecha, vientre ancho y
  punta afilada.

Más detalle en los comentarios de `animaciones.py`.

## Personalizar

Las posiciones de las flores y del origen de los tallos están en el diccionario
`COORDENADAS` al inicio de `animaciones.py`; los colores, en las constantes
`VERDE_*`.
