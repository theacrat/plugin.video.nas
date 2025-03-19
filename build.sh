#!/bin/sh

DIR_NAME=$(basename "$(pwd)")
VERSION=$(grep -o '<addon[^>]*version="[^"]*"' addon.xml | head -1 | grep -o 'version="[^"]*"' | cut -d'"' -f2)
ZIP_NAME="${DIR_NAME}_${VERSION}.zip"

cd ..
zip -r "$DIR_NAME/$ZIP_NAME" "$DIR_NAME/addon.xml" "$DIR_NAME/resources" -x "*/__pycache__/*"
cd "$DIR_NAME"