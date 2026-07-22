#!/usr/bin/env bash
# setup.sh — Configura o ambiente de desenvolvimento com venv
set -e

VENV_DIR=".venv"

echo "🐍 Criando ambiente virtual em $VENV_DIR ..."
python3 -m venv "$VENV_DIR"

echo "📦 Instalando dependências ..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r requirements.txt --quiet

echo ""
echo "✅ Ambiente pronto!"
echo ""
echo "Para ativar:  source .venv/bin/activate"
echo "Para rodar:   python main.py"
