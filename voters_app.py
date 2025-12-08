from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

DBS = ["voters_1.db", "voters.db"]            # both DB files (update paths if needed)
SUGGESTION_LIMIT = 25                         # max suggestions returned

# --------------------------
# Malayalam -> simple Latin phonetic mapper
# --------------------------
# This mapping is intentionally conservative: it covers most common letters and vowel signs.
# You can extend it for corner cases in your data.
ML_TO_LATIN = {
    # vowels
    "അ":"a","ആ":"aa","ഇ":"i","ഈ":"ee","ഉ":"u","ഊ":"oo",
    "എ":"e","ഏ":"ee","ഐ":"ai","ഒ":"o","ഓ":"oo","ഔ":"au",

    # consonants
    "ക":"ka","ഖ":"kha","ഗ":"ga","ഘ":"gha","ങ":"nga",
    "ച":"cha","ഛ":"chha","ജ":"ja","ഝ":"jha","ഞ":"nja",
    "ട":"ta","ഠ":"tha","ഡ":"da","ഢ":"dha","ണ":"na",
    "ത":"tha","ഥ":"thha","ദ":"dha","ധ":"dhha","ന":"na",
    "പ":"pa","ഫ":"pha","ബ":"ba","ഭ":"bha","മ":"ma",
    "യ":"ya","ര":"ra","ല":"la","വ":"va","ശ":"sha",
    "ഷ":"sha","സ":"sa","ഹ":"ha","ള":"la","ഴ":"zha","റ":"ra",

    # vowel signs (matras) - mapped to letters to form correct sounds
    "ാ": "a", "ി": "i", "ീ": "ee", "ു": "u", "ൂ": "oo",
    "െ": "e", "േ": "ee", "ൈ": "ai", "ൊ": "o", "ോ": "oo", "ൗ": "au",

    # special marks
    "്": "",        # virama - remove (half consonant marker)
    "ം": "m",       # anusvara
    "ഃ": "h",       # visarga
    "െ": "e",
}

# fallback: unknown char -> remove
def ml_to_phonetic(ml_text: str) -> str:
    """Convert Malayalam text to a simplified Latin phonetic key."""
    out = []
    for ch in ml_text.strip():
        if ch.isspace():
            out.append("")  # keep parts separated, we'll join
            continue
        mapped = ML_TO_LATIN.get(ch)
        if mapped is None:
            # try to drop diacritics or combine clusters by ignoring unknowns
            # or preserve ASCII as is
            if re.match(r"[A-Za-z0-9]", ch):
                out.append(ch)
            else:
                # unknown Malayalam char - skip gracefully
                out.append("")
        else:
            out.append(mapped)
    # join and normalise: collapse multiple empties -> single separator
    joined = "".join(out)
    # remove non alphanumeric characters, normalize repeated letters a bit
    normalized = re.sub(r'[^a-z0-9]+', '', joined.lower())
    # compress runs like 'aa'->'a' for simpler matching? keep double vowels for clarity
    normalized = re.sub(r'(.)\1{2,}', r'\1\1', normalized)  # avoid huge repeats
    return normalized


# --------------------------
# Levenshtein distance & ratio
# --------------------------
def levenshtein_distance(a: str, b: str) -> int:
    """Classic DP Levenshtein distance. Reasonably fast for short strings."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    # ensure a is the shorter for memory efficiency?
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * lb
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1,         # deletion
                         cur[j-1] + 1,       # insertion
                         prev[j-1] + cost)   # substitution
        prev = cur
    return prev[lb]

def similarity_ratio(a: str, b: str) -> float:
    """Normalized similarity in [0.0, 1.0] where 1.0 is exact match."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    dist = levenshtein_distance(a, b)
    maxlen = max(len(a), len(b))
    if maxlen == 0:
        return 0.0
    return max(0.0, 1.0 - dist / maxlen)


# --------------------------
# Build phonetic index (cache)
# --------------------------
# Structure:
# {
#   'house_name': {
#       'phonetic_key1': set(['മാല', 'മാള']) ,
#       ...
#   },
#   'name': { ... }
# }
PHONETIC_INDEX = {
    "house_name": {},
    "name": {}
}

def load_phonetic_index():
    """Load distinct Malayalam values from both DBs and populate PHONETIC_INDEX."""
    for column in ("house_name", "name"):
        mapping = {}
        seen = set()
        for db in DBS:
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            try:
                cur.execute(f"SELECT DISTINCT {column} FROM voters WHERE {column} IS NOT NULL AND {column} <> ''")
                rows = cur.fetchall()
            except Exception:
                rows = []
            conn.close()

            for (val,) in rows:
                if not val:
                    continue
                val = val.strip()
                if val in seen:
                    continue
                seen.add(val)
                key = ml_to_phonetic(val)
                if not key:
                    continue
                mapping.setdefault(key, set()).add(val)
        PHONETIC_INDEX[column] = mapping

# initialize at startup
load_phonetic_index()


# --------------------------
# Helpers for DB search for house_no
# --------------------------
def search_house_no(query):
    """Search house_no by substring across DBs and return unique values."""
    q = query.strip()
    results = set()
    for db in DBS:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        try:
            cur.execute("SELECT DISTINCT house_no FROM voters WHERE house_no IS NOT NULL AND house_no <> ''")
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        for (val,) in rows:
            if not val:
                continue
            if q in str(val):
                results.add(str(val))
    return sorted(results)


# --------------------------
# Suggestion engine (core)
# --------------------------
def suggest_for_text_column(user_input: str, column: str, max_results=SUGGESTION_LIMIT):
    """
    user_input: English phonetic typed by user (e.g., 'padettu', 'malayil', 'shaji')
    column: 'house_name' or 'name'
    returns: list of dicts: [{'value': <malayalam string>, 'score': float, 'phonetic': <key>}...]
    """
    q = re.sub(r'[^a-z0-9]+', '', user_input.lower())
    if not q:
        return []

    index = PHONETIC_INDEX.get(column, {})
    candidates = []

    # 1) substring/starts-with quick pass on phonetic keys
    for key, ml_set in index.items():
        # check starts-with (strong signal)
        if key.startswith(q):
            score = 1.0  # best possible match (exact start)
        elif q in key:
            score = 0.88  # good partial match
        else:
            # compute fuzzy similarity ratio
            sim = similarity_ratio(q, key)
            score = sim * 0.9  # slightly lower weight for fuzzy vs starts-with
        # only consider if score not too low
        if score >= 0.45:
            for ml in ml_set:
                candidates.append((ml, key, score))

    # If no candidates found with threshold, relax threshold and do global fuzzy check
    if not candidates:
        for key, ml_set in index.items():
            sim = similarity_ratio(q, key)
            if sim >= 0.30:  # looser
                for ml in ml_set:
                    candidates.append((ml, key, sim * 0.8))

    # score adjustments: exact phonetic equality between q and key -> boost
    normalized = q
    results_map = {}
    for ml, key, base_score in candidates:
        key_norm = key
        sc = base_score
        if normalized == key_norm:
            sc = max(sc, 0.995)
        # if user input equals ml (rare if user enters Malayalam) give top priority
        if user_input.strip() == ml.strip():
            sc = 0.9999
        # collect best score per Malayalam string
        prev = results_map.get(ml)
        if (prev is None) or (sc > prev):
            results_map[ml] = sc

    # Turn into sorted list by score desc and then by lexical
    sorted_results = sorted(results_map.items(), key=lambda kv: (-kv[1], kv[0]))
    out = []
    for ml, sc in sorted_results[:max_results]:
        out.append({"value": ml, "score": round(float(sc), 4), "phonetic": None})
    return out


# --------------------------
# API endpoints & templates
# --------------------------
@app.route("/")
def index():
    # we supply lists so the selects can be prepopulated if you want
    # but suggestions use phonetic engine.
    # For initial page load we send small lists from PHONETIC_INDEX
    house_names = sorted({v for key in PHONETIC_INDEX.get("house_name", {}) for v in PHONETIC_INDEX["house_name"][key]})
    names = sorted({v for key in PHONETIC_INDEX.get("name", {}) for v in PHONETIC_INDEX["name"][key]})
    # fetch house_no distinct across DBs (brief)
    house_nos = search_house_no("")  # returns all (may be large)
    return render_template("index.html", house_names=house_names[:100], house_nos=house_nos[:200], names=names[:100])


@app.route("/api/search_suggestions")
def api_search_suggestions():
    """
    Query params:
      q: user typed string (English phonetic)
      type: 'house_name' | 'house_no' | 'name'
    Returns JSON: list of suggestions (ordered best first)
      Each suggestion: { value: <malayalam string or house_no>, score: <0..1> }
    """
    raw_q = request.args.get("q", "").strip()
    search_type = request.args.get("type", "name").strip()
    if not raw_q:
        return jsonify([])

    if search_type == "house_no":
        # simple substring match on house_no
        matches = search_house_no(raw_q)
        # convert to objects with score 1.0 for exact-ish, 0.8 for contains
        out = []
        for v in matches[:SUGGESTION_LIMIT]:
            score = 1.0 if raw_q == str(v) else 0.7
            out.append({"value": v, "score": score})
        return jsonify(out)

    if search_type not in ("house_name", "name"):
        search_type = "name"

    # use fuzzy phonetic search
    suggestions = suggest_for_text_column(raw_q, search_type, max_results=SUGGESTION_LIMIT)

    # attach phonetic keys optionally for debugging (disabled here)
    return jsonify(suggestions)


@app.route("/comparison")
def comparison():
    return render_template("comparison.html")


# Simplified compare_results (keeps same behaviour as earlier)
@app.route("/compare_results", methods=["POST"])
def compare_results():
    comparison_type = request.form.get("comparison_type")
    value = request.form.get("value", "").strip()
    if not comparison_type or not value:
        return "Invalid comparison parameters", 400

    # Query both DBs for exact equality (value expected is Malayalam string or house_no)
    voters1 = []
    voters2 = []
    for i, db in enumerate(DBS):
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT * FROM voters WHERE {comparison_type} = ?", (value,))
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        if i == 0:
            voters1 = rows
        else:
            voters2 = rows

    set1 = set(tuple(r) for r in voters1)
    set2 = set(tuple(r) for r in voters2)
    common = list(set1 & set2)
    unique1 = list(set1 - set2)
    unique2 = list(set2 - set1)

    headers = ["Serial", "Name", "Guardian Name", "House No", "House Name", "Gender", "Age", "Voter ID"]
    return render_template("compare_results.html",
                           comparison_type=comparison_type, value=value,
                           voters1=voters1, voters2=voters2,
                           common=common, unique1=unique1, unique2=unique2,
                           headers=headers)


@app.route("/details", methods=["POST"])
def details():
    # keep existing details logic (name transliteration -> phonetic search)
    booth_no = request.form.get("booth_no", "")
    house_name = request.form.get("house_name", "").strip()
    house_no = request.form.get("house_no", "").strip()
    name = request.form.get("name", "").strip()

    db = "voters_1.db" if booth_no == "1" else "voters.db"

    if house_name:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM voters WHERE house_name = ?", (house_name,))
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        groups = {}
        for r in rows:
            hno = r[3] if len(r) > 3 else ""
            groups.setdefault(hno, []).append(r)
        return render_template("details.html", house_name=house_name, groups=groups, booth_no=booth_no)

    if house_no:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM voters WHERE house_no = ?", (house_no,))
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        return render_template("details.html", house_no=house_no, voters=rows, booth_no=booth_no)

    if name:
        # Convert user-typed English to lower alnum, then scan phonetic index to find Malayalam equivalent(s)
        q = re.sub(r'[^a-z0-9]+', '', name.lower())
        # search phonetic index
        results = suggest_for_text_column(q, "name", max_results=10)
        # take first Malayalam suggestion(s) and fetch rows from DB
        mal_values = [r["value"] for r in results]
        rows_all = []
        for mv in mal_values:
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            try:
                cur.execute("SELECT * FROM voters WHERE name = ?", (mv,))
                rows = cur.fetchall()
            except Exception:
                rows = []
            conn.close()
            rows_all.extend(rows)
        return render_template("details.html", name=name, voters=rows_all, booth_no=booth_no)

    return "No valid filter selected", 400


if __name__ == "__main__":
    # For development use: app.run(debug=True)
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
