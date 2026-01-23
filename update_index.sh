#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 - <<'PY'
import glob, json, re

files = sorted(glob.glob("*.png"))
with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

arr = "const IMAGES = " + json.dumps(files, ensure_ascii=False, indent=2) + ";"
html2 = re.sub(r"const IMAGES = \[[\s\S]*?\];", arr, html, count=1)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html2)

print(f"OK: index.html actualizado con {len(files)} imágenes")
PY
