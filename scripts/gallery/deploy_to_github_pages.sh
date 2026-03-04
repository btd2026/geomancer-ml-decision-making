#!/bin/bash
# Deploy gallery to GitHub Pages (docs/gallery/)
# Run this from the project root

set -e

GALLERY_SRC="gallery/deployed"
GALLERY_DEST="docs/gallery"

echo "Deploying gallery to GitHub Pages..."

# Create destination directory
mkdir -p "$GALLERY_DEST"

# Copy gallery files
cp "$GALLERY_SRC/gallery_data.json" "$GALLERY_DEST/"
cp "$GALLERY_SRC/gallery.js" "$GALLERY_DEST/"
cp "$GALLERY_SRC/styles.css" "$GALLERY_DEST/"
cp "$GALLERY_SRC/wandb_multiselect_gallery.html" "$GALLERY_DEST/index.html"

# Copy images
rm -rf "$GALLERY_DEST/images"
cp -r "$GALLERY_SRC/images" "$GALLERY_DEST/"

# Count files
IMAGE_COUNT=$(ls "$GALLERY_DEST/images/" | wc -l)
echo "Deployed:"
echo "  - gallery_data.json"
echo "  - gallery.js"
echo "  - styles.css"
echo "  - index.html"
echo "  - $IMAGE_COUNT images"
echo ""
echo "To publish: git add docs/gallery/ && git commit -m 'Update gallery' && git push"
