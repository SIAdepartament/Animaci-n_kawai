# -*- coding: utf-8 -*-
"""
animaciones.py
==============
Módulo con toda la lógica procedural de "Generación de animación".

Cada etapa es un *generador*: va produciendo fotogramas (objetos `Lienzo`)
uno a uno. `main.py` solo tiene que dibujarlos y esperar entre ellos.

    Etapa 1 -> mariposa que se "imprime" celda a celda   (etapa_mariposa)
    Etapa 2 -> tallos y espirales que crecen hacia arriba (etapa_tallos)
    Etapa 3 -> lirios que se abren en las puntas          (etapa_flores)

-------------------------------------------------------------------------
MATEMÁTICA DEL ESPACIO DE DISEÑO (lo más importante para entender el código)
-------------------------------------------------------------------------
Una celda de terminal NO es cuadrada: mide aproximadamente 1 unidad de ancho
por 2 de alto. Si dibujáramos círculos "por celda" saldrían óvalos estirados.

Para evitarlo, toda la geometría se define en un *espacio de diseño*
isótropo (X e Y miden lo mismo):

    D = 2 * alto            # alto total en "unidades visuales" (fila = 2)
    X = (x + 0.5 - ancho/2) / D     # horizontal, 0 = centro, rango ~ [-0.425, 0.425]
    Y = (y + 0.5) * 2 / D           # vertical,   0 = arriba, 1 = abajo

y la conversión inversa (diseño -> celda) es:

    x = floor(ancho/2 + X * D)
    y = floor(Y * D / 2)

Así un círculo de radio 0.07 en diseño es un círculo de verdad en pantalla,
sin importar el tamaño de la terminal: todo escala con `alto`.

Relación de aspecto del lienzo: ancho = ASPECTO * alto (1.7), por lo que el
ancho en diseño es 1.7*alto / (2*alto) = 0.85 -> X va de -0.425 a +0.425.
"""

import math
import random
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constantes de layout (la composición de la imagen 1, en espacio de diseño)
# ---------------------------------------------------------------------------
ASPECTO = 1.7      # ancho / alto del lienzo en celdas
ALTO_MAX = 44      # tope de filas para no pasarse en pantallas enormes
ALTO_MIN = 18      # por debajo de esto la figura pierde detalle

# Diccionario de coordenadas: dónde vive cada elemento (X, Y en espacio de diseño)
COORDENADAS = {
    # Punto donde nacen los tallos (justo sobre la cabeza de la mariposa)
    "origen_tallos": (0.0, 0.60),
    # Puntas de los tallos = centros de los círculos azules de la imagen 1.
    # Ordenadas de abajo hacia arriba para que las flores abran "de adentro hacia afuera".
    "puntas": [
        (-0.11, 0.35), (0.12, 0.36),
        (-0.185, 0.24), (0.20, 0.25),
        (-0.29, 0.13), (0.30, 0.14),
    ],
    # Centro del cuerpo de la mariposa (para las venas radiales de las alas)
    "mariposa_pivote": (0.0, 0.69),
    # Fila (en diseño) del texto final "para ti"
    "texto_final_y": 0.03,
}

# Paletas ANSI de 256 colores (código para \033[38;5;Nm)
VERDE_ALA = [155, 150, 114, 71]    # de claro a oscuro
VERDE_OSCURO = [22, 236, 234]
VERDE_TALLO = 34
VERDE_ESPIRAL = 71
VERDE_PUNTA = 120


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def suave(t):
    """Smoothstep: acelera y frena (0->1). Da el aspecto 'fluido' al crecimiento."""
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def inv_suave(s):
    """Inversa de `suave` por bisección: ¿en qué tiempo t el progreso vale s?"""
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if suave(mid) < s:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def char_direccion(dx, dy):
    """
    Elige el carácter que mejor representa un trazo con dirección (dx, dy).
    Ojo: en pantalla Y crece hacia abajo, por eso se invierte dy.
    """
    ang = math.degrees(math.atan2(-dy, dx)) % 180
    if ang < 22.5 or ang >= 157.5:
        return "-"
    if ang < 67.5:
        return "/"
    if ang < 112.5:
        return "|"
    return "\\"


def dimensionar(cols, filas):
    """Alto del lienzo que cabe en la terminal (dejando 2 filas libres)."""
    alto = min(filas - 2, ALTO_MAX, int((cols - 1) / ASPECTO))
    return max(alto, ALTO_MIN)


# ---------------------------------------------------------------------------
# Lienzo: la "matriz de fotograma"
# ---------------------------------------------------------------------------
class Lienzo:
    """Matriz alto x ancho; cada celda es None o una tupla (caracter, color_256)."""

    def __init__(self, alto):
        self.alto = alto
        self.ancho = int(alto * ASPECTO)
        self.D = 2 * alto
        self.celdas = [[None] * self.ancho for _ in range(alto)]

    # --- conversiones celda <-> espacio de diseño (ver docstring del módulo) ---
    def a_diseno(self, x, y):
        return (x + 0.5 - self.ancho / 2) / self.D, (y + 0.5) * 2 / self.D

    def a_celda(self, X, Y):
        return int(math.floor(self.ancho / 2 + X * self.D)), int(math.floor(Y * self.D / 2))

    def poner(self, x, y, car, color):
        if 0 <= x < self.ancho and 0 <= y < self.alto:
            self.celdas[y][x] = (car, color)

    def poner_diseno(self, X, Y, car, color):
        x, y = self.a_celda(X, Y)
        self.poner(x, y, car, color)

    def copia(self):
        nuevo = Lienzo.__new__(Lienzo)
        nuevo.alto, nuevo.ancho, nuevo.D = self.alto, self.ancho, self.D
        nuevo.celdas = [fila[:] for fila in self.celdas]
        return nuevo


def renderizar(lienzo, cols, filas):
    """
    Convierte un Lienzo en el texto ANSI a imprimir, centrado en la terminal.

    Centrado:
        margen_izq = (cols - ancho) // 2
        margen_sup = (filas - alto) // 2
    Solo se emite un código de color cuando cambia, para no saturar la consola.
    """
    margen_izq = max(0, (cols - lienzo.ancho) // 2)
    margen_sup = max(0, (filas - lienzo.alto) // 2)
    sangria = " " * margen_izq
    lineas = []
    for fila in lienzo.celdas:
        partes = [sangria]
        color_actual = None
        for celda in fila:
            if celda is None:
                partes.append(" ")
                continue
            car, color = celda
            if color != color_actual:
                partes.append(f"\033[38;5;{color}m")
                color_actual = color
            partes.append(car)
        partes.append("\033[0m")
        lineas.append("".join(partes))
    return "\n" * margen_sup + "\n".join(lineas)


# ===========================================================================
# ETAPA 1 - MARIPOSA (área roja de la imagen 1)
# ===========================================================================
def _elipse_rotada(u, Y, cu, cY, a, b, ang_deg):
    """
    Pertenencia a una elipse rotada. Devuelve (valor, p):
      valor < 1  -> el punto está dentro (0 centro, 1 borde)
      p          -> coordenada a lo largo del eje mayor (para zonas de color)
    Se rota el punto al sistema de la elipse:
        p =  dx*cos(a) + dy*sin(a)
        q = -dx*sin(a) + dy*cos(a)
        valor = (p/a)^2 + (q/b)^2
    """
    ang = math.radians(ang_deg)
    dx, dy = u - cu, Y - cY
    p = dx * math.cos(ang) + dy * math.sin(ang)
    q = -dx * math.sin(ang) + dy * math.cos(ang)
    return (p / a) ** 2 + (q / b) ** 2, p


def generar_mariposa(L):
    """
    Devuelve {(x, y): (caracter, color)} con la mariposa completa.

    Simetría: se evalúa con u = |X|, así el ala izquierda es espejo exacto
    de la derecha sin duplicar fórmulas.
    """
    px, py = COORDENADAS["mariposa_pivote"]
    celdas = {}
    for y in range(L.alto):
        for x in range(L.ancho):
            X, Y = L.a_diseno(x, y)
            u = abs(X)

            # Cuerpo y cabeza: columna central estrecha
            if u < 0.011 and 0.655 < Y < 0.86:
                celdas[(x, y)] = ("@", 233)
                continue

            # Ala superior (clara) y ala inferior (con la punta oscura)
            v_sup, _ = _elipse_rotada(u, Y, 0.12, 0.585, 0.17, 0.075, -35)
            v_inf, p_inf = _elipse_rotada(u, Y, 0.11, 0.79, 0.14, 0.07, 55)
            # Cola de golondrina: elipse fina vertical
            v_col, _ = _elipse_rotada(u, Y, 0.115, 0.895, 0.012, 0.038, 90)

            valor, oscura = None, False
            if v_col < 1:
                valor, oscura = v_col, True
            elif v_inf < 1:
                valor, oscura = v_inf, p_inf > -0.02   # parte exterior = oscura
            elif v_sup < 1:
                valor = v_sup
            if valor is None:
                continue

            # Venas radiales + nervaduras concéntricas desde el pivote del cuerpo
            ang = math.atan2(Y - py, u)
            dist = math.hypot(u, Y - py)
            vena = abs(math.sin(ang * 9)) > 0.9 or abs(math.sin(dist * 60)) > 0.96

            if oscura:
                car = "@" if not vena else "#"
                color = VERDE_OSCURO[0] if valor < 0.6 else VERDE_OSCURO[1]
            else:
                car = "#" if vena else "%"
                if valor > 0.88:                 # contorno del ala
                    car, color = "@", 28
                elif valor < 0.3:
                    color = VERDE_ALA[0]
                elif valor < 0.6:
                    color = VERDE_ALA[1]
                else:
                    color = VERDE_ALA[2]
            celdas[(x, y)] = (car, color)
    return celdas


def etapa_mariposa(L, fondo, n_frames=70):
    """
    Efecto 'impresión': se recorren las celdas en orden de lectura (fila a
    fila, de izquierda a derecha) y en cada fotograma se imprime un bloque.
    Progresión: celdas_por_frame = ceil(total / n_frames).
    El bloque recién impreso se muestra brillante (cabezal de impresora).
    """
    celdas = sorted(generar_mariposa(L).items(), key=lambda kv: (kv[0][1], kv[0][0]))
    total = len(celdas)
    paso = max(1, math.ceil(total / n_frames))
    for i in range(0, total, paso):
        bloque = celdas[i:i + paso]
        for (x, y), (car, color) in bloque:
            fondo.poner(x, y, car, color)
        frame = fondo.copia()
        for (x, y), _ in bloque:
            frame.poner(x, y, "#", 231)     # cabezal brillante
        yield frame
    yield fondo.copia()


# ===========================================================================
# ETAPA 2 - TALLOS Y ESPIRALES (área amarilla de la imagen 1)
# ===========================================================================
@dataclass
class Trazo:
    """Un trazo que crece: lista de puntos (X, Y) en orden de crecimiento."""
    puntos: list
    chars: list          # carácter por punto (según la tangente)
    color: int
    inicio: float        # instante (0..T) en que empieza a crecer
    duracion: float
    cabeza: bool = True  # ¿mostrar punta brillante mientras crece?


def _bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        u**3 * p0[0] + 3*u*u*t * p1[0] + 3*u*t*t * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3*u*u*t * p1[1] + 3*u*t*t * p2[1] + t**3 * p3[1],
    )


def _muestrear_tallo(origen, punta, lado, fase, n=260):
    """
    Curva de Bézier cúbica origen->punta + ondulación senoidal perpendicular.
        ondulacion(t) = amp * sin(2*pi*1.5*t + fase) * sin(pi*t)
    El factor sin(pi*t) vale 0 en ambos extremos, así el tallo nace y
    termina exactamente en los puntos dados.
    Devuelve lista de (X, Y, tx, ty) con la tangente unitaria de cada punto.
    """
    p0, p3 = origen, punta
    p1 = (p0[0] + lado * 0.03, p0[1] - 0.20)
    p2 = (p3[0] - lado * 0.08, p3[1] + 0.20)
    base = [_bezier(p0, p1, p2, p3, i / (n - 1)) for i in range(n)]
    pts = []
    for i, (X, Y) in enumerate(base):
        a = base[max(i - 1, 0)]
        b = base[min(i + 1, n - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        norma = math.hypot(tx, ty) or 1.0
        tx, ty = tx / norma, ty / norma
        t = i / (n - 1)
        off = 0.014 * math.sin(2 * math.pi * 1.5 * t + fase) * math.sin(math.pi * t)
        pts.append((X - ty * off, Y + tx * off, tx, ty))   # normal = (-ty, tx)
    return pts


def _espiral(P, tangente, lado_n, r0, vueltas=2.4, n=90):
    """
    Zarcillo en espiral que nace en P y se enrolla.
    Se coloca el centro C a distancia r0 de P (sobre la normal) y se recorre
        punto(th) = C + r(th) * (cos(phi0 + d*th), sin(phi0 + d*th))
        r(th)     = r0 * (1 - 0.88 * th / th_max)     # radio decreciente
    El signo `d` se elige para que la espiral arranque en la misma dirección
    en la que crece el tallo (producto punto con la tangente > 0).
    """
    tx, ty = tangente
    nx, ny = -ty * lado_n, tx * lado_n          # normal con signo
    cx, cy = P[0] + nx * r0, P[1] + ny * r0     # centro de la espiral
    phi0 = math.atan2(P[1] - cy, P[0] - cx)
    d = 1
    tang_circulo = (-math.sin(phi0), math.cos(phi0))
    if tang_circulo[0] * tx + tang_circulo[1] * ty < 0:
        d = -1
    th_max = vueltas * 2 * math.pi
    pts = []
    for i in range(n):
        th = th_max * i / (n - 1)
        r = r0 * (1 - 0.88 * th / th_max)
        pts.append((cx + r * math.cos(phi0 + d * th), cy + r * math.sin(phi0 + d * th)))
    return pts


def _chars_de_puntos(pts):
    chars = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        chars.append(char_direccion(b[0] - a[0], b[1] - a[1]))
    return chars


def construir_trazos():
    """
    Genera todos los trazos de la etapa 2 con su calendario de crecimiento.
    Las espirales y hojas brotan cuando el tallo (con su easing) ya pasó por
    el punto de unión: inicio_rama = inicio_tallo + dur * inv_suave(s).
    """
    rng = random.Random(11)
    origen = COORDENADAS["origen_tallos"]
    trazos = []
    for i, punta in enumerate(COORDENADAS["puntas"]):
        lado = -1 if punta[0] < 0 else 1
        inicio = 0.04 * (i // 2)
        dur = 0.62
        muestras = _muestrear_tallo(origen, punta, lado, fase=rng.uniform(0, 6.28))
        pts = [(m[0], m[1]) for m in muestras]
        trazos.append(Trazo(pts, _chars_de_puntos(pts), VERDE_TALLO, inicio, dur))

        for k, (s, r0) in enumerate([(0.22, 0.030), (0.42, 0.027), (0.62, 0.024), (0.80, 0.020)]):
            idx = int(s * (len(muestras) - 1))
            X, Y, tx, ty = muestras[idx]
            sentido = 1 if (k % 2 == 0) else -1
            # primera espiral hacia afuera del eje central
            if lado * (-ty * sentido) < 0:
                sentido = -sentido
            esp = _espiral((X, Y), (tx, ty), sentido, r0)
            t0 = inicio + dur * inv_suave(s)
            trazos.append(Trazo(esp, _chars_de_puntos(esp), VERDE_ESPIRAL, t0, 0.22))
            # hojita en la unión
            hoja = [(X + dx * 0.012, Y + dy * 0.012) for dx, dy in ((1, 0), (0, -1), (-1, 0), (0, 1))]
            trazos.append(Trazo(hoja, ["%"] * 4, 28, t0, 0.06, cabeza=False))
    return trazos


def _dibujar_trazos(frame, L, trazos, t):
    for tr in trazos:
        prog = suave((t - tr.inicio) / tr.duracion)
        n = int(len(tr.puntos) * prog)
        if n <= 0:
            continue
        for (X, Y), car in zip(tr.puntos[:n], tr.chars[:n]):
            L_x, L_y = L.a_celda(X, Y)
            frame.poner(L_x, L_y, car, tr.color)
        if tr.cabeza and prog < 1.0:
            X, Y = tr.puntos[n - 1]
            frame.poner_diseno(X, Y, "*", VERDE_PUNTA)


def etapa_tallos(L, fondo, n_frames=95):
    """Crecimiento fotograma a fotograma: t recorre 0..T y cada trazo avanza según suave()."""
    trazos = construir_trazos()
    T = max(tr.inicio + tr.duracion for tr in trazos)
    for f in range(n_frames):
        t = T * f / (n_frames - 1)
        frame = fondo.copia()
        _dibujar_trazos(frame, L, trazos, t)
        yield frame
    _dibujar_trazos(fondo, L, trazos, T)      # deja el estado final en el fondo
    yield fondo.copia()


# ===========================================================================
# ETAPA 3 - LIRIOS (círculos azules de la imagen 1, forma de la imagen 2)
# ===========================================================================
def _angulo_dif(a, b):
    """Diferencia angular mínima absoluta entre a y b (0..pi)."""
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def _tepalo(th, phi, s, semiancho):
    """
    Forma de un pétalo en coordenadas polares (th = ángulo, s = r/largo).
    El ancho angular permitido en cada radio es
        dmax(s) = semiancho * sin(pi * s^0.7)^0.8
    -> 0 en la base (s=0), máximo hacia el 40-50 % y 0 de nuevo en la punta
    (s=1): un pétalo de lirio con punta afilada.
    Devuelve (dentro, borde) con borde = d/dmax (0 eje, 1 contorno).
    """
    dmax = semiancho * math.sin(math.pi * min(s, 1.0) ** 0.7) ** 0.8
    d = _angulo_dif(th, phi)
    if dmax <= 1e-6 or d >= dmax:
        return False, 1.0
    return True, d / dmax


def _dibujar_lirio(frame, L, cx, cy, R, b, rot_deg):
    """
    Dibuja un lirio en el centro (cx, cy) de diseño con radio máximo R.
    b = progreso de floración 0..1:  0-0.25 capullo verde, 0.25-1 apertura.
    Capas (de atrás hacia adelante):
        1) tres sépalos externos  -> amarillo suave
        2) tres pétalos internos  -> blanco
        3) garganta               -> verde oliva
        4) seis estambres         -> marrón oscuro con anteras '@'
    """
    if b <= 0:
        return
    x0, y0 = L.a_celda(cx - R, cy - R)
    x1, y1 = L.a_celda(cx + R, cy + R)

    # ---- capullo --------------------------------------------------------
    if b < 0.25:
        k = 0.4 + 0.6 * (b / 0.25)
        rx, ry = R * 0.14 * k, R * 0.40 * k
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                X, Y = L.a_diseno(x, y)
                if ((X - cx) / rx) ** 2 + ((Y - cy + ry * 0.4) / ry) ** 2 <= 1:
                    L_car = "#" if abs(X - cx) < rx * 0.5 else "%"
                    frame.poner(x, y, L_car, 71 if L_car == "#" else 107)
        return

    o = suave((b - 0.25) / 0.75)
    largo = R * (0.25 + 0.75 * o)
    rot = math.radians(rot_deg) - math.pi / 2          # un pétalo apunta arriba
    fases_ext = [rot + k * 2 * math.pi / 3 for k in range(3)]
    fases_int = [f + math.pi / 3 for f in fases_ext]

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            X, Y = L.a_diseno(x, y)
            dx, dy = X - cx, Y - cy
            r = math.hypot(dx, dy)
            if r > largo:
                continue
            s = r / largo
            th = math.atan2(dy, dx)
            celda = None

            for phi in fases_ext:                      # capa 1: sépalos
                dentro, borde = _tepalo(th, phi, s, math.radians(31))
                if dentro:
                    car = ":" if borde > 0.8 else ("#" if s < 0.45 else "%")
                    color = 192 if s < 0.4 else (229 if s < 0.75 else 228)
                    celda = (car, color)
            for phi in fases_int:                      # capa 2: pétalos
                dentro, borde = _tepalo(th, phi, s, math.radians(34))
                if dentro:
                    car = ":" if borde > 0.8 else ("#" if s < 0.45 else "%")
                    color = 194 if s < 0.35 else (231 if s < 0.75 else 255)
                    celda = (car, color)
            if r < 0.15 * largo:                       # capa 3: garganta
                celda = ("@", 106)
            if celda:
                frame.poner(x, y, celda[0], celda[1])

    # ---- estambres (solo cuando la flor ya está bastante abierta) --------
    if o > 0.35:
        e = suave((o - 0.35) / 0.65)
        for j in range(6):
            ang = rot + j * math.pi / 3 + math.pi / 6 + 0.25 * math.sin(j * 2.1)
            fin = largo * 0.62 * e
            pasos = max(3, int(fin * L.D * 1.6))
            ultimo = None
            for k in range(pasos + 1):
                rr = 0.12 * largo + (fin - 0.12 * largo) * k / pasos
                X = cx + rr * math.cos(ang)
                Y = cy + rr * math.sin(ang)
                frame.poner_diseno(X, Y, char_direccion(math.cos(ang), math.sin(ang)), 130)
                ultimo = (X, Y)
            if ultimo:                                  # antera oscura
                frame.poner_diseno(ultimo[0], ultimo[1], "@", 52)
                frame.poner_diseno(ultimo[0] + 0.008 * math.cos(ang),
                                   ultimo[1] + 0.008 * math.sin(ang), "@", 88)


def etapa_flores(L, fondo, n_frames=75, radio=0.072):
    """
    Cada lirio florece con un retraso escalonado:
        b_i(t) = clamp((t - i*0.09) / 0.55, 0, 1)
    Así las flores más cercanas al centro abren primero y la ola avanza
    hacia las puntas exteriores.
    """
    rng = random.Random(5)
    flores = []
    for i, (X, Y) in enumerate(COORDENADAS["puntas"]):
        flores.append((X, Y, rng.uniform(-35, 35), i * 0.09))
    for f in range(n_frames):
        t = f / (n_frames - 1)
        frame = fondo.copia()
        for X, Y, rot, retraso in flores:
            b = min(max((t - retraso) / 0.55, 0.0), 1.0)
            _dibujar_lirio(frame, L, X, Y, radio, b, rot)
        yield frame
    final = fondo.copia()
    for X, Y, rot, _ in flores:
        _dibujar_lirio(final, L, X, Y, radio, 1.0, rot)
    fondo.celdas = final.celdas
    yield fondo.copia()


# ===========================================================================
# EPÍLOGO - texto "para ti" (aparece letra por letra)
# ===========================================================================
def etapa_texto(L, fondo, texto="para ti"):
    X = 0.0
    y = max(0, int(COORDENADAS["texto_final_y"] * L.D / 2))
    letras = " ".join(texto)                    # espaciado para que se lea mejor
    x_ini = L.ancho // 2 - len(letras) // 2
    for i, car in enumerate(letras):
        if car != " ":
            fondo.poner(x_ini + i, y, car, 231)
        yield fondo.copia()
