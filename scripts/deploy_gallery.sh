#!/bin/bash
# Deploy Gallery - Automated dataset updating for PHATE Gallery
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PHATE_RESULTS_DIR="/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/phate_results"
GALLERY_DEPLOYED_DIR="$PROJECT_ROOT/gallery/deployed"
DOCS_DIR="$PROJECT_ROOT/docs"

echo "🔄 PHATE Gallery Deployment Pipeline"
echo "===================================="

# Step 1: Generate gallery data from PHATE results
echo "📊 Step 1: Generating gallery data..."
cd "$SCRIPT_DIR/gallery"
python generate_gallery_data.py \
    --phate-results-dir "$PHATE_RESULTS_DIR" \
    --output-dir "$GALLERY_DEPLOYED_DIR" \
    --copy-images \
    --verbose

if [ $? -ne 0 ]; then
    echo "❌ Failed to generate gallery data"
    exit 1
fi

# Step 2: Copy to docs directory for GitHub Pages
echo "📁 Step 2: Copying to docs directory..."
cp "$GALLERY_DEPLOYED_DIR/gallery_data_new.json" "$DOCS_DIR/gallery_data.json"

# Copy new images (preserve existing ones)
echo "🖼️  Step 3: Updating images..."
mkdir -p "$DOCS_DIR/images"
rsync -av --ignore-existing "$GALLERY_DEPLOYED_DIR/images/" "$DOCS_DIR/images/"

# Step 4: Git operations
echo "📝 Step 4: Committing changes..."
cd "$PROJECT_ROOT"

# Check what changed
NEW_DATASETS=$(jq -r '.summary.total_datasets' "$DOCS_DIR/gallery_data.json")
NEW_RUNS=$(jq -r '.summary.total_runs' "$DOCS_DIR/gallery_data.json")

echo "📈 New statistics:"
echo "   - Total datasets: $NEW_DATASETS"
echo "   - Total runs: $NEW_RUNS"

# Add changes
git add docs/gallery_data.json
git add docs/images/

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "✅ No changes detected - gallery is already up to date"
else
    # Commit with summary
    COMMIT_MSG="Update gallery: $NEW_DATASETS datasets, $NEW_RUNS runs

$(jq -r '.summary.algorithm_counts | to_entries[] | "- \(.key): \(.value)"' "$DOCS_DIR/gallery_data.json")

Generated at: $(date)"

    git commit -m "$COMMIT_MSG"

    echo "🚀 Step 5: Pushing to GitHub..."
    git push

    echo "✅ Gallery deployment complete!"
    echo "🌐 Changes will be live at: https://btd2026.github.io/geomancer-ml-decision-making/gallery.html"
    echo "⏱️  GitHub Pages update: ~2-3 minutes"
fi

echo ""
echo "📋 Summary:"
echo "   - Datasets: $NEW_DATASETS"
echo "   - Runs: $NEW_RUNS"
echo "   - Algorithms: $(jq -r '.summary.algorithm_counts | keys | join(", ")' "$DOCS_DIR/gallery_data.json")"
