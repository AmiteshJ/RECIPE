"""
Recipe Lens - Flask Backend
Serves all pages and provides JSON API endpoints.
"""

import os
import json
import uuid
import base64
import tempfile
from pathlib import Path
from flask import (
    Flask, render_template, request, jsonify,
    send_from_directory, abort
)

# Add parent to path so models import works
import sys
sys.path.insert(0, str(Path(__file__).parent))

from models.matcher import (
    extract_vegetables_from_text,
    detect_vegetables_from_image,
    suggest_recipes,
    get_recipe_by_id,
    get_filter_categories,
    get_nutrient_labels,
    get_nutrient_units,
    RECIPES,
)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

UPLOAD_TMP = Path(tempfile.gettempdir()) / "recipe_lens_uploads"
UPLOAD_TMP.mkdir(exist_ok=True)

# ── Page routes ──────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template("index.html")


@app.route("/voice-chef")
def voice_chef():
    return render_template("voice_chef.html")


@app.route("/vision-chef")
def vision_chef():
    return render_template("vision_chef.html")


@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        abort(404)
    return render_template("recipe.html", recipe_id=recipe_id)

# ── API: Voice Chef ───────────────────────────────────────────────────────────

@app.route("/api/voice/process", methods=["POST"])
def api_voice_process():
    """Process spoken text and extract vegetables."""
    data = request.get_json(force=True)
    transcript = data.get("transcript", "").strip()

    if not transcript:
        return jsonify({"error": "No transcript provided"}), 400

    vegetables = extract_vegetables_from_text(transcript)

    return jsonify({
        "transcript": transcript,
        "vegetables": vegetables,
        "count": len(vegetables)
    })


@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    """Suggest recipes given a list of vegetables and optional filter."""
    data = request.get_json(force=True)
    vegetables = data.get("vegetables", [])
    filter_key = data.get("filter", None)

    if not vegetables:
        return jsonify({"error": "No vegetables provided"}), 400

    results = suggest_recipes(vegetables, filter_key)

    # Build response payload
    cards = []
    for r in results:
        recipe = r["recipe"]
        cards.append({
            "id": recipe["id"],
            "name": recipe["name"],
            "description": recipe["description"],
            "cuisine": recipe["cuisine"],
            "difficulty": recipe["difficulty"],
            "total_time": recipe["total_time"],
            "prep_time": recipe["prep_time"],
            "cook_time": recipe["cook_time"],
            "calories": recipe["calories_per_serving"],
            "tags": recipe["tags"],
            "score": r["score"],
            "matched": r["exact_matches"] + r["fuzzy_matches"],
            "missing": r["missing_vegs"],
            "coverage_pct": r["coverage_pct"],
            "nutrients": recipe["nutrients"],
            "image": recipe["image"],
        })

    return jsonify({
        "cards": cards,
        "total": len(cards),
        "detected_vegetables": vegetables,
        "filter_applied": filter_key
    })


# ── API: Vision Chef ──────────────────────────────────────────────────────────

@app.route("/api/vision/detect", methods=["POST"])
def api_vision_detect():
    """Detect vegetables from an uploaded or captured image."""
    tmp_path = None
    try:
        # Handle both file upload and base64 encoded data URL
        if request.content_type and "multipart" in request.content_type:
            file = request.files.get("image")
            if not file:
                return jsonify({"error": "No image file provided"}), 400
            tmp_path = UPLOAD_TMP / f"{uuid.uuid4().hex}.jpg"
            file.save(str(tmp_path))
        else:
            data = request.get_json(force=True)
            img_data = data.get("image_data", "")
            if not img_data:
                return jsonify({"error": "No image data provided"}), 400
            # Strip data URL prefix if present
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            img_bytes = base64.b64decode(img_data)
            tmp_path = UPLOAD_TMP / f"{uuid.uuid4().hex}.jpg"
            tmp_path.write_bytes(img_bytes)

        detections = detect_vegetables_from_image(str(tmp_path))
        vegetables = [d["vegetable"] for d in detections if d.get("confidence", 0) > 10]

        return jsonify({
            "detections": detections,
            "vegetables": vegetables,
            "count": len(vegetables)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


# ── API: Recipe detail ────────────────────────────────────────────────────────

@app.route("/api/recipe/<int:recipe_id>")
def api_recipe_detail(recipe_id):
    """Return full recipe data including scaled ingredients."""
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404

    servings = request.args.get("servings", recipe["base_servings"], type=int)
    servings = max(1, min(servings, 100))
    scale = servings / recipe["base_servings"]

    # Scale ingredients
    scaled_ingredients = []
    for ing in recipe["ingredients"]:
        scaled_qty = round(ing["quantity"] * scale, 2)
        # Format nicely
        if scaled_qty == int(scaled_qty):
            scaled_qty = int(scaled_qty)
        scaled_ingredients.append({
            **ing,
            "scaled_quantity": scaled_qty,
            "servings": servings
        })

    # Scale nutrients
    scaled_nutrients = {
        k: round(v * scale, 2)
        for k, v in recipe["nutrients"].items()
    }

    return jsonify({
        **recipe,
        "requested_servings": servings,
        "scale_factor": round(scale, 4),
        "scaled_ingredients": scaled_ingredients,
        "scaled_nutrients": scaled_nutrients,
        "nutrient_labels": get_nutrient_labels(),
        "nutrient_units": get_nutrient_units(),
    })


# ── API: Filters ──────────────────────────────────────────────────────────────

@app.route("/api/filters")
def api_filters():
    return jsonify(get_filter_categories())


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Recipe Lens is running!")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)
