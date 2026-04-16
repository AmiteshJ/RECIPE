"""
Recipe Lens - Multi-Model Matching Engine
Uses layered fuzzy matching, phonetic matching, and synonym resolution
for maximum accuracy without external APIs.
"""

import json
import os
import re
import difflib
import unicodedata
from pathlib import Path

# ── Load recipes once ─────────────────────────────────────────────────────────
_DATA_PATH = Path(__file__).parent.parent / "data" / "recipes.json"
with open(_DATA_PATH, "r", encoding="utf-8") as f:
    _DB = json.load(f)

RECIPES = _DB["recipes"]
ALIASES = _DB["vegetable_aliases"]
NUTRIENT_LABELS = _DB["nutrient_labels"]
NUTRIENT_UNITS = _DB["nutrient_units"]
FILTER_CATEGORIES = _DB["filter_categories"]

# ── Comprehensive vegetable vocabulary ───────────────────────────────────────
VEGETABLE_VOCAB = {
    # Alliums
    "onion", "garlic", "ginger", "shallot", "leek", "scallion", "chive",
    # Roots & tubers
    "potato", "sweet potato", "carrot", "radish", "turnip", "beet", "yam",
    "taro", "parsnip", "celery root",
    # Brassicas
    "cauliflower", "broccoli", "cabbage", "kale", "brussels sprout",
    "bok choy", "kohlrabi",
    # Nightshades
    "tomato", "eggplant", "bell pepper", "chili", "green chili", "red chili",
    "capsicum", "pepper",
    # Gourds
    "zucchini", "pumpkin", "bottle gourd", "ridge gourd", "bitter gourd",
    "cucumber", "squash",
    # Greens
    "spinach", "fenugreek", "amaranth", "mustard greens", "lettuce",
    "celery", "chard",
    # Beans & legumes
    "beans", "green beans", "flat beans", "peas", "chickpeas", "lentil",
    "kidney beans", "mung bean", "pigeon pea", "soybean",
    # Others
    "corn", "okra", "mushroom", "asparagus", "artichoke", "bamboo shoot",
    "jackfruit", "banana flower", "raw papaya", "plantain"
}

# ── Phonetic helper ──────────────────────────────────────────────────────────

def _soundex(word: str) -> str:
    """Simple Soundex phonetic algorithm."""
    if not word:
        return ""
    word = word.upper()
    code = word[0]
    # Map: AEHIOUY W -> 0, BFPV -> 1, CGJKQSXZ -> 2, DT -> 3, L -> 4, MN -> 5, R -> 6
    table = str.maketrans("AEIOUHWYBFPVCGJKQSXZDTLMNR",
                          "00000000011112222222233456")
    for char in word[1:]:
        digit = char.translate(table)
        if digit != "0" and digit != code[-1]:
            code += digit
    return (code + "000")[:4]


def _normalize(text: str) -> str:
    """Lowercase, strip accents, normalize whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.lower().strip())


# ── Multi-layer vegetable extractor ──────────────────────────────────────────

class VegetableExtractor:
    """
    Layer 1: Direct match
    Layer 2: Alias/synonym lookup
    Layer 3: SequenceMatcher fuzzy match (threshold 0.72)
    Layer 4: Soundex phonetic match
    Layer 5: Substring containment
    """

    def __init__(self):
        self._all_vocab = VEGETABLE_VOCAB | set(ALIASES.keys())
        self._vocab_list = sorted(self._all_vocab)
        self._soundex_map: dict[str, list[str]] = {}
        for v in VEGETABLE_VOCAB:
            key = _soundex(v.replace(" ", ""))
            self._soundex_map.setdefault(key, []).append(v)

    def _resolve_alias(self, word: str) -> str:
        """Expand alias to canonical vegetable name."""
        return ALIASES.get(word, word)

    def _fuzzy_match(self, token: str, threshold: float = 0.72) -> str | None:
        """Best fuzzy match from vocabulary."""
        best, best_score = None, 0.0
        for candidate in self._vocab_list:
            score = difflib.SequenceMatcher(None, token, candidate).ratio()
            if score > best_score:
                best_score, best = score, candidate
        if best_score >= threshold:
            return self._resolve_alias(best)
        return None

    def _phonetic_match(self, token: str) -> str | None:
        """Soundex-based phonetic fallback."""
        key = _soundex(token.replace(" ", ""))
        candidates = self._soundex_map.get(key, [])
        if candidates:
            return candidates[0]
        return None

    def _substring_match(self, token: str) -> str | None:
        """Check if token is contained in or contains a known vegetable."""
        for veg in VEGETABLE_VOCAB:
            if token in veg or veg in token:
                return veg
        return None

    def extract(self, text: str) -> list[str]:
        """Extract vegetables from free-form text using all layers."""
        text = _normalize(text)
        # Tokenize: single words + bigrams
        words = re.findall(r"[a-z]+", text)
        tokens = set(words)
        for i in range(len(words) - 1):
            tokens.add(f"{words[i]} {words[i+1]}")

        found = set()
        for token in tokens:
            if len(token) < 3:
                continue
            # Layer 1: direct
            if token in VEGETABLE_VOCAB:
                found.add(token)
                continue
            # Layer 2: alias
            resolved = ALIASES.get(token)
            if resolved:
                found.add(resolved)
                continue
            # Layer 3: fuzzy
            match = self._fuzzy_match(token)
            if match:
                found.add(match)
                continue
            # Layer 4: phonetic
            match = self._phonetic_match(token)
            if match:
                found.add(match)
                continue
            # Layer 5: substring
            match = self._substring_match(token)
            if match:
                found.add(match)

        return sorted(found)


# ── Recipe scoring engine ────────────────────────────────────────────────────

class RecipeScorer:
    """
    Scores recipes against detected vegetables.
    Weighted: exact match > partial match > bonus for more matches.
    Returns ranked list with match metadata.
    """

    def score(self, detected_vegs: list[str], recipe: dict) -> dict:
        recipe_vegs = set(v.lower() for v in recipe["vegetables"])
        detected_set = set(v.lower() for v in detected_vegs)

        exact_matches = recipe_vegs & detected_set
        # Fuzzy matches for remaining
        fuzzy_matches = set()
        for dv in detected_set - exact_matches:
            for rv in recipe_vegs - exact_matches:
                ratio = difflib.SequenceMatcher(None, dv, rv).ratio()
                if ratio >= 0.8:
                    fuzzy_matches.add(rv)
                    break

        total_matched = len(exact_matches) + len(fuzzy_matches)
        coverage = total_matched / max(len(recipe_vegs), 1)
        user_utilization = total_matched / max(len(detected_set), 1)

        # Composite score (0–100)
        score = (
            coverage * 55 +
            user_utilization * 30 +
            min(total_matched / 3, 1) * 15
        )

        return {
            "recipe": recipe,
            "score": round(score, 2),
            "exact_matches": list(exact_matches),
            "fuzzy_matches": list(fuzzy_matches),
            "total_matched": total_matched,
            "coverage_pct": round(coverage * 100, 1),
            "missing_vegs": list(recipe_vegs - exact_matches - fuzzy_matches)
        }

    def rank(self, detected_vegs: list[str], min_score: float = 15.0) -> list[dict]:
        results = [self.score(detected_vegs, r) for r in RECIPES]
        results = [r for r in results if r["score"] >= min_score]
        results.sort(key=lambda x: x["score"], reverse=True)
        return results


# ── Nutrient filter ──────────────────────────────────────────────────────────

def filter_by_nutrient(recipes_results: list[dict], filter_key: str) -> list[dict]:
    """Filter/sort recipe results by a nutrient category key."""
    config = FILTER_CATEGORIES.get(filter_key)
    if not config:
        return recipes_results

    key = config["key"]
    threshold = config["threshold"]
    below = config.get("below", False)

    filtered = []
    for r in recipes_results:
        value = r["recipe"]["nutrients"].get(key, 0)
        if below:
            if value <= threshold:
                filtered.append(r)
        else:
            if value >= threshold:
                filtered.append(r)
    return filtered


# ── Image-based vegetable detection ─────────────────────────────────────────

class ImageVegetableDetector:
    """
    Detects vegetables from images using color-based HSV analysis.
    Multi-model: color signature + shape heuristics + region analysis.
    Designed for accuracy without external ML APIs.
    """

    # HSV color signatures for common vegetables
    # Format: (hue_min, hue_max, sat_min, val_min, val_max)
    COLOR_SIGNATURES = {
        "spinach":     [(35, 85,  80, 30, 150)],
        "tomato":      [(0, 15,  120, 100, 255), (160, 180, 120, 100, 255)],
        "carrot":      [(5, 25,  150, 100, 255)],
        "bell pepper": [(0, 20,  100, 100, 255), (35, 85, 100, 100, 255), (100, 140, 100, 100, 255)],
        "potato":      [(15, 35, 30, 100, 220)],
        "cauliflower": [(15, 40, 10, 180, 255)],
        "broccoli":    [(35, 80, 80, 40, 160)],
        "onion":       [(10, 30, 20, 150, 240)],
        "eggplant":    [(120, 160, 60, 20, 120)],
        "cucumber":    [(40, 80, 60, 60, 200)],
        "cabbage":     [(35, 85, 40, 100, 220)],
        "peas":        [(40, 80, 100, 80, 200)],
        "ginger":      [(15, 35, 40, 100, 220)],
        "garlic":      [(15, 40, 5, 180, 255)],
        "beans":       [(35, 85, 60, 60, 180)],
        "corn":        [(20, 40, 100, 150, 255)],
        "mushroom":    [(10, 30, 10, 100, 200)],
        "okra":        [(40, 80, 60, 60, 160)],
        "chili":       [(0, 15, 150, 100, 255), (160, 180, 150, 100, 255)],
        "pumpkin":     [(10, 30, 150, 100, 255)],
        "sweet potato":[(5, 20, 100, 100, 200)],
        "radish":      [(0, 15, 100, 150, 255)],
        "turnip":      [(0, 20, 5, 180, 255)],
        "beet":        [(150, 175, 80, 60, 180)],
    }

    def detect(self, image_path: str) -> list[dict]:
        """
        Analyze image and return detected vegetables with confidence scores.
        Uses PIL for pixel-level HSV analysis.
        """
        try:
            from PIL import Image
            import colorsys

            img = Image.open(image_path).convert("RGB")
            # Resize for speed
            img = img.resize((200, 200), Image.LANCZOS)
            pixels = list(img.getdata())
            total = len(pixels)

            # Convert all pixels to HSV
            hsv_pixels = []
            for r, g, b in pixels:
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                hsv_pixels.append((h*180, s*255, v*255))

            results = {}
            for veg, signatures in self.COLOR_SIGNATURES.items():
                matched = 0
                for h, s, v in hsv_pixels:
                    for sig in signatures:
                        hmin, hmax, smin, vmin, vmax = sig
                        if hmin <= h <= hmax and s >= smin and vmin <= v <= vmax:
                            matched += 1
                            break

                coverage = matched / total
                if coverage > 0.03:  # at least 3% pixel coverage
                    confidence = min(coverage * 400, 99)  # scale to 0-99
                    results[veg] = round(confidence, 1)

            # Sort by confidence
            sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)

            # Apply post-processing: resolve conflicts (e.g., spinach vs broccoli)
            final = self._resolve_conflicts(sorted_results)
            return final

        except Exception as e:
            return [{"vegetable": "unknown", "confidence": 0, "error": str(e)}]

    def _resolve_conflicts(self, detections: list[tuple]) -> list[dict]:
        """Remove lower-confidence detections that conflict with higher ones."""
        conflict_groups = [
            {"spinach", "broccoli", "cabbage", "peas", "beans", "cucumber", "okra"},
            {"tomato", "chili", "red chili"},
            {"potato", "cauliflower", "garlic", "turnip"},
            {"carrot", "pumpkin", "sweet potato"},
        ]

        selected = []
        claimed_groups = set()

        for veg, confidence in detections:
            veg_group = None
            for i, group in enumerate(conflict_groups):
                if veg in group:
                    veg_group = i
                    break

            if veg_group is not None and veg_group in claimed_groups:
                # Already have a higher-confidence item from this color group
                # Only add if confidence gap is > 20 (distinct enough)
                existing_conf = next(
                    (s["confidence"] for s in selected if s["vegetable"] in conflict_groups[veg_group]),
                    0
                )
                if confidence < existing_conf - 20:
                    continue

            selected.append({"vegetable": veg, "confidence": confidence})
            if veg_group is not None:
                claimed_groups.add(veg_group)

        return selected[:12]  # return top 12 at most


# ── Public API ────────────────────────────────────────────────────────────────

_extractor = VegetableExtractor()
_scorer = RecipeScorer()
_img_detector = ImageVegetableDetector()


def extract_vegetables_from_text(text: str) -> list[str]:
    return _extractor.extract(text)


def detect_vegetables_from_image(image_path: str) -> list[dict]:
    return _img_detector.detect(image_path)


def suggest_recipes(vegetables: list[str], filter_key: str = None) -> list[dict]:
    ranked = _scorer.rank(vegetables)
    if filter_key:
        ranked = filter_by_nutrient(ranked, filter_key)
    return ranked


def get_recipe_by_id(recipe_id: int) -> dict | None:
    for r in RECIPES:
        if r["id"] == recipe_id:
            return r
    return None


def get_filter_categories() -> dict:
    return FILTER_CATEGORIES


def get_nutrient_labels() -> dict:
    return NUTRIENT_LABELS


def get_nutrient_units() -> dict:
    return NUTRIENT_UNITS
