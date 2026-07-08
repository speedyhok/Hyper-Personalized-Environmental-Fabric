#!/usr/bin/env bash
# exit on error
set -o errexit

echo "=================================================================="
echo "          Starting H-SEF Render Production Build"
echo "=================================================================="

# Upgrade pip
python -m pip install --upgrade pip

# Install PyTorch CPU-only version (saves disk space and RAM)
echo "Installing lightweight CPU-only PyTorch..."
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install standard dependencies
echo "Installing core dependencies..."
pip install -r requirements.txt

echo "=================================================================="
echo "          H-SEF Build Completed Successfully!"
echo "=================================================================="
