#!/bin/bash
# Install optional dependencies for OCR corrector
# These are recommended but not required - the script has fallbacks

echo "Installing optional dependencies for parliamentary_ocr_corrector.py..."
echo ""

# Try to install pyenchant
echo "1/2 Installing pyenchant (modern English dictionary)..."
pip install pyenchant 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ pyenchant installed successfully"
else
    echo "⚠ pyenchant installation failed (will use fallback)"
fi

echo ""

# Try to install python-Levenshtein
echo "2/2 Installing python-Levenshtein (fast edit distance)..."
pip install python-Levenshtein 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ python-Levenshtein installed successfully"
else
    echo "⚠ python-Levenshtein installation failed (will use slower fallback)"
fi

echo ""
echo "Done! You can now run:"
echo "  python parliamentary_ocr_corrector.py"
