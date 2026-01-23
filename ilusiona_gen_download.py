#!/usr/bin/env python3
# ==============================================================================
# Script Name : ilusiona_gen_download.py
# Description : Generador de números de 14 dígitos (formato Ilusiona) y volcado
#               a fichero de salida con timestamp (igual que ilusiona_gen.py),
#               y además descarga un PNG (Interleaved 2 of 5) desde free-barcode.com
#               por cada línea/número generado en el fichero.
#
# FUNCIONALIDAD PRINCIPAL (IGUAL QUE ANTES):
# - Pregunta al usuario:
#     * Parte fija (6 dígitos)
#     * Número de serie inicial (0..999)
#     * Cantidad de números a generar (N)
# - Genera N números (14 dígitos) con:
#     FFFFFF + SSS + TTTT + C
#   donde:
#     * FFFFFF = parte fija (6 dígitos)
#     * SSS    = serie secuencial (3 dígitos, 000..999)
#     * TTTT   = tickets aleatorio [116..951] formateado a 4 dígitos (0116..0951)
#     * C      = CRC (GS1 Mod 10, pesos 3 y 1) sobre los 13 dígitos base
# - Crea el fichero: ilusiona_yyyymmddhhmmss.txt (directorio actual)
# - Una línea por cada número (14 dígitos)
#
# FUNCIONALIDAD AÑADIDA:
# - Tras generar el fichero, descarga un PNG por cada número:
#     ./<NUMERO_14>.png
# - Si el PNG ya existe y no está vacío, lo salta.
# - Verifica que el contenido descargado sea realmente PNG (cabecera PNG).
#
# REQUISITOS:
# - Python 3.x (stdlib). No requiere requests.
# ==============================================================================

import datetime
import secrets
import os
import time
import urllib.parse
import urllib.request
from typing import Tuple


def gs1_mod10_check_digit(number_str: str) -> str:
    """
    GS1 Mod 10 (pesos 3 y 1):
    - Se calcula sobre number_str (sin el dígito de control).
    - Desde la derecha: pesos 3,1,3,1...
    - Dígito = (10 - (suma % 10)) % 10
    """
    total = 0
    weight = 3  # el dígito más a la derecha pesa 3 en GS1
    for ch in reversed(number_str):
        d = ord(ch) - ord("0")
        total += d * weight
        weight = 1 if weight == 3 else 3
    return str((10 - (total % 10)) % 10)


def ask_digits(prompt: str, length: int) -> str:
    while True:
        s = input(prompt).strip()
        if len(s) == length and s.isdigit():
            return s
        print(f"ERROR: debe ser un número de exactamente {length} dígitos.")


def ask_int(prompt: str, min_v: int = None, max_v: int = None) -> int:
    while True:
        s = input(prompt).strip()
        if not s.isdigit():
            print("ERROR: introduce un entero.")
            continue
        v = int(s)
        if min_v is not None and v < min_v:
            print(f"ERROR: debe ser >= {min_v}.")
            continue
        if max_v is not None and v > max_v:
            print(f"ERROR: debe ser <= {max_v}.")
            continue
        return v


def build_barcode_url(code: str) -> str:
    """
    Replica los parámetros del script bash:
      BC2="17" BC3="3" BC4="1.05" BC5="1" BC6="1" BC7="Arial" BC8="15" BC9="1"
    """
    base_url = "https://free-barcode.com/barcode.asp"
    params = {
        "bc1": code,
        "bc2": "17",
        "bc3": "3",
        "bc4": "1.05",
        "bc5": "1",
        "bc6": "1",
        "bc7": "Arial",
        "bc8": "15",
        "bc9": "1",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def is_png_file(path: str) -> bool:
    # Cabecera PNG: 89 50 4E 47 0D 0A 1A 0A
    try:
        with open(path, "rb") as f:
            sig = f.read(8)
        return sig == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def download_png(code: str, out_file: str, timeout_s: int = 30, retries: int = 2, sleep_s: float = 0.5) -> Tuple[bool, str]:
    """
    Descarga el PNG para 'code' en 'out_file'.
    Devuelve (ok, mensaje).
    - Si el fichero ya existe y no está vacío, lo considera OK y no descarga.
    - Descarga a fichero temporal y valida cabecera PNG antes de renombrar.
    """
    if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
        return True, f"OK (ya existe): {out_file}"

    url = build_barcode_url(code)
    tmp_file = out_file + ".tmp"

    # User-Agent para evitar bloqueos simples del servidor.
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ilusiona_gen_download/1.0",
        "Accept": "image/png,image/*;q=0.9,*/*;q=0.8",
    }

    last_err = ""
    for attempt in range(1, retries + 2):  # retries=2 => intentos 1..3
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = resp.read()

            # Escribe temporal
            with open(tmp_file, "wb") as f:
                f.write(data)

            # Validar PNG
            if is_png_file(tmp_file):
                os.replace(tmp_file, out_file)
                return True, f"OK: {out_file}"
            else:
                # Probablemente HTML / error del sitio
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
                return False, f"ERROR: descargado pero no parece PNG (quizá HTML). Código={code}"

        except Exception as e:
            last_err = str(e)
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except OSError:
                pass
            if attempt < (retries + 2):
                time.sleep(sleep_s)
                continue

    return False, f"ERROR: fallo descargando {code}. Último error: {last_err}"


def main():
    # --- Parte original (igual) ---
    fixed = ask_digits("Parte fija (6 dígitos): ", 6)
    start_serial = ask_int("Número de serie inicial (ej. 101): ", min_v=0, max_v=999)
    qty = ask_int("Cantidad de números a generar: ", min_v=1)

    SERIAL_WIDTH = 3
    TICKETS_MIN = 116
    TICKETS_MAX = 951
    TICKETS_WIDTH = 4

    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    out_file = f"ilusiona_{ts}.txt"

    generated = []

    with open(out_file, "w", encoding="utf-8") as f:
        for i in range(qty):
            serial_val = start_serial + i
            if serial_val > 999:
                raise SystemExit(f"ERROR: la serie se sale de 3 dígitos (última={serial_val}).")

            serial = f"{serial_val:0{SERIAL_WIDTH}d}"

            tickets_val = secrets.randbelow(TICKETS_MAX - TICKETS_MIN + 1) + TICKETS_MIN
            tickets = f"{tickets_val:0{TICKETS_WIDTH}d}"

            base_13 = fixed + serial + tickets  # 6 + 3 + 4 = 13
            crc = gs1_mod10_check_digit(base_13)

            full_14 = base_13 + crc
            f.write(full_14 + "\n")
            generated.append(full_14)

    print(f"OK. Generados {qty} números en: {out_file}")

    # --- Nueva parte: descarga de PNGs ---
    print("\nDescargando PNGs desde free-barcode.com (Interleaved 2 of 5)...")
    total = 0
    ok = 0
    skip = 0  # (reservado si quisieras filtrar; aquí realmente no hay skip salvo no numérico)
    fail = 0

    for code in generated:
        total += 1

        if not code.isdigit():
            # No debería ocurrir porque generamos dígitos, pero lo dejamos por seguridad.
            print(f"WARN: ignorado (no numérico): {code}")
            skip += 1
            continue

        png_file = f"./{code}.png"
        print(f"Descargando: {code} -> {png_file}")

        success, msg = download_png(code, png_file, timeout_s=30, retries=2, sleep_s=0.5)
        print(msg)
        if success:
            ok += 1
        else:
            fail += 1

    print("\nResumen descarga:")
    print(f"  Procesados: {total}")
    print(f"  OK:         {ok}")
    print(f"  Ignorados:  {skip}")
    print(f"  Fallos:     {fail}")
    print("")


if __name__ == "__main__":
    main()
