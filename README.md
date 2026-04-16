# Recipe Lens 🍽️

> An AI-powered kitchen assistant that detects vegetables and suggests recipes via voice or camera — no external AI APIs required.

---

## Project Structure

```
recipe_lens/
├── app.py                   # Flask backend + API routes
├── requirements.txt
├── data/
│   └── recipes.json         # Recipe database (add 100+ recipes here)
├── models/
│   └── matcher.py           # Multi-layer matching engine
└── templates/
    ├── index.html           # Landing page
    ├── voice_chef.html      # Voice input + recipe suggestions
    ├── vision_chef.html     # Image upload/camera + detection
    └── recipe.html          # Recipe detail + Recipe Book (voice guided)
```

---

## Quick Start

```bash
cd recipe_lens
pip install flask pillow numpy
python app.py
```

Open: **http://localhost:5000**

---

## Features

### 🎙️ Voice Chef
- Browser-native speech recognition (Web Speech API)
- Multi-layer vegetable extraction:
  - Layer 1: Exact word match against vocabulary of 60+ vegetables
  - Layer 2: Hindi/regional alias resolution (aloo→potato, gobi→cauliflower, etc.)
  - Layer 3: Fuzzy string matching (SequenceMatcher, threshold 0.72)
  - Layer 4: Soundex phonetic matching
  - Layer 5: Substring containment
- Supports English + Hinglish (e.g., "I have aloo, gobi, aur tamatar")
- Keyboard fallback if microphone unavailable

### 📷 Vision Chef
- Upload images or capture via live camera
- Color-based HSV vegetable detection (no ML library required)
- 20+ vegetable color signatures
- Conflict resolution for similar-colored vegetables
- User can toggle detected vegetables before searching

### 🃏 Recipe Flashcards
- Sorted by match score (exact match + coverage + utilization)
- Nutrient filter bar: High Protein, High Fiber, Vitamin C Rich, Iron Rich, etc.
- Shows matched/missing vegetables per recipe
- Nutrient bars (protein, fiber, vitamins)

### ⚖️ Serving Scaler
- Adjust servings (1–100) with ± buttons
- All ingredient quantities update in real-time via API call
- Nutrients shown per serving

### 📖 Recipe Book (Full-Screen Cooking Mode)
- Full-screen step-by-step recipe reader
- Text-to-Speech narration (Web Speech Synthesis API)
- Voice command control:
  - "next" / "previous" / "back" — navigation
  - "repeat" — re-narrate step
  - "tip" — read the pro tip
  - "start timer" / "stop timer" — control step timer
  - "done" — mark step done
- Step progress tracker (sidebar + top bar)
- Per-step countdown timers
- Chef's tips highlighted per step
- Completion screen with celebration

---

## Adding More Recipes

Edit `data/recipes.json` and add entries to the `"recipes"` array.

Each recipe needs:
```json
{
  "id": <unique int>,
  "name": "Recipe Name",
  "description": "...",
  "cuisine": "Indian/Asian/Italian/...",
  "difficulty": "Easy/Medium/Hard",
  "prep_time": 15,
  "cook_time": 25,
  "total_time": 40,
  "base_servings": 4,
  "calories_per_serving": 200,
  "vegetables": ["potato", "onion", "tomato"],
  "tags": ["vegetarian", "gluten-free"],
  "nutrients": {
    "protein": 5.0,
    "carbohydrates": 30.0,
    "fat": 8.0,
    "fiber": 4.0,
    "vitamin_c": 45,
    "iron": 2.5,
    "calcium": 80
  },
  "ingredients": [
    { "id": "ing_1", "name": "Potato (cubed)", "quantity": 3, "unit": "pieces", "per_serving": 0.75 }
  ],
  "steps": [
    {
      "step": 1,
      "title": "Step Title",
      "instruction": "Detailed instruction text...",
      "duration_seconds": 300,
      "tip": "Pro chef tip..."
    }
  ]
}
```

The `per_serving` field = `quantity / base_servings`. The API uses this for scaling.

---

## Technical Architecture

### Backend (Python/Flask)
- `app.py` — Routes, request handling, image processing
- `models/matcher.py` — All intelligence layers:
  - `VegetableExtractor` — Multi-layer text NLP
  - `RecipeScorer` — Weighted match scoring
  - `ImageVegetableDetector` — HSV color analysis via PIL

### Frontend (HTML/CSS/JavaScript)
- Vanilla JS — no framework dependencies
- Web Speech API — voice input + text-to-speech
- MediaDevices API — camera access
- FileReader API — image upload
- Fetch API — async backend calls

### Accuracy Strategy (No External AI)
1. **Vocabulary coverage** — 60+ vegetables + 50+ aliases
2. **Fuzzy matching** — catches typos and near-matches
3. **Phonetic matching** — catches pronunciation-based mismatches
4. **HSV color segmentation** — per-pixel color signature matching
5. **Conflict resolution** — handles same-color vegetables by confidence gap

---

## Browser Requirements
- Chrome 25+ or Edge 79+ (best Speech API support)
- Firefox (speech recognition may be limited)
- HTTPS required for camera access on production

---

## License
MIT — Built for real-world use, not demo purposes.
