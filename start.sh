#!/usr/bin/env bash
# MedStock ERP - Mac/Linux uchun ishga tushirish
cd "$(dirname "$0")"
echo "=========================================="
echo "           MedStock ERP"
echo "  Ombor, sotuv va qaytarish tizimi"
echo "=========================================="
PY=python3
command -v $PY >/dev/null 2>&1 || PY=python
echo "[1/2] Kutubxonalar o'rnatilmoqda..."
$PY -m pip install -r requirements.txt --quiet
echo "[2/2] Dastur ishga tushmoqda... http://localhost:5000  (admin / admin123)"
( sleep 3; (open http://localhost:5000 || xdg-open http://localhost:5000) >/dev/null 2>&1 ) &
$PY server.py
