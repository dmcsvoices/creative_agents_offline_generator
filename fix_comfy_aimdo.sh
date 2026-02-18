#!/bin/bash
#
# Fix Script: comfy_aimdo Module Installation
#
# This script fixes the ModuleNotFoundError for comfy_aimdo by ensuring
# it's installed in the correct Python environment location.
#
# Background:
# - ComfyUI requires comfy_aimdo (AI Model Dynamic Offloader) as of recent updates
# - Due to path aliasing, pip sometimes installs to /Users/tikbalang instead of
#   /Volumes/Tikbalang2TB/Users/tikbalang
# - This script manually copies the module to the correct location
#

set -e  # Exit on error

echo "============================================================"
echo "ComfyUI comfy_aimdo Fix Script"
echo "============================================================"
echo ""

PYTHON_BIN="/Volumes/Tikbalang2TB/Users/tikbalang/comfy_env/bin/python"
PIP_BIN="/Volumes/Tikbalang2TB/Users/tikbalang/comfy_env/bin/pip"
SOURCE_DIR="/Users/tikbalang/comfy_env/lib/python3.12/site-packages"
TARGET_DIR="/Volumes/Tikbalang2TB/Users/tikbalang/comfy_env/lib/python3.12/site-packages"

echo "Step 1: Check if comfy_aimdo is installed..."
if $PIP_BIN list | grep -q "comfy-aimdo"; then
    VERSION=$($PIP_BIN show comfy-aimdo | grep Version | awk '{print $2}')
    echo "✓ comfy-aimdo version $VERSION is installed via pip"
else
    echo "✗ comfy-aimdo is NOT installed"
    echo ""
    echo "Installing comfy-aimdo..."
    $PIP_BIN install comfy-aimdo
    echo "✓ comfy-aimdo installed"
fi

echo ""
echo "Step 2: Check if module can be imported..."
if $PYTHON_BIN -c "import comfy_aimdo" 2>/dev/null; then
    echo "✓ comfy_aimdo can be imported successfully"
    echo ""
    echo "✅ Everything is working! No fix needed."
    exit 0
else
    echo "✗ comfy_aimdo cannot be imported"
    echo ""
    echo "Step 3: Attempting manual copy from alternate location..."

    if [ -d "$SOURCE_DIR/comfy_aimdo" ]; then
        echo "Found comfy_aimdo in alternate location: $SOURCE_DIR"
        echo "Copying to correct location: $TARGET_DIR"

        # Copy both comfy_aimdo directory and dist-info
        cp -r "$SOURCE_DIR"/comfy_aimdo* "$TARGET_DIR/"

        echo "✓ Files copied successfully"

        # Verify import works now
        if $PYTHON_BIN -c "import comfy_aimdo; import comfy_aimdo.torch" 2>/dev/null; then
            echo "✓ comfy_aimdo import verified"
            echo ""
            echo "✅ Fix completed successfully!"
            exit 0
        else
            echo "✗ Import still fails after copying"
            echo ""
            echo "❌ Manual intervention required"
            exit 1
        fi
    else
        echo "✗ Could not find comfy_aimdo in alternate location"
        echo ""
        echo "Trying to reinstall..."
        $PIP_BIN install --force-reinstall --no-deps comfy-aimdo

        # Try import again
        if $PYTHON_BIN -c "import comfy_aimdo" 2>/dev/null; then
            echo "✓ Reinstall successful"
            echo ""
            echo "✅ Fix completed!"
            exit 0
        else
            # If still doesn't work, try the copy again
            if [ -d "$SOURCE_DIR/comfy_aimdo" ]; then
                cp -r "$SOURCE_DIR"/comfy_aimdo* "$TARGET_DIR/"

                if $PYTHON_BIN -c "import comfy_aimdo" 2>/dev/null; then
                    echo "✓ Fix completed after reinstall + copy"
                    exit 0
                fi
            fi

            echo ""
            echo "❌ Could not fix the issue automatically"
            echo ""
            echo "Please try manually:"
            echo "  1. Check Python environment: $PYTHON_BIN"
            echo "  2. Check site-packages: $TARGET_DIR"
            echo "  3. Ensure comfy-aimdo is installed: $PIP_BIN install comfy-aimdo"
            exit 1
        fi
    fi
fi
