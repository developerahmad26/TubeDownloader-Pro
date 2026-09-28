"""Title Rewriter and Rephraser Engine for TubeDownloader Pro."""

import json
import os
import re
import urllib.request
from config import BASE_DIR

RULES_FILE = os.path.join(BASE_DIR, "title_rules.json")

DEFAULT_RULES = {
    "rewrite_mode": "smart_rephrase",  # 'smart_rephrase', 'hook', 'reorder', 'ai_gemini', 'clean_only'
    "hook_style": "Dramatic Hook",     # 'Dramatic Hook', 'Vlog Story', 'Question Hook', 'None'
    "gemini_api_key": "",              # Optional Google Gemini API key for true LLM rewriting
    "remove_emojis": True,
    "remove_hashtags": True,
    "remove_mentions": True,
    "remove_resolution_tags": True,
    "clean_separators": True,
    "custom_replacements": {},         # {"old_phrase": "new_phrase"}
}

# Regex to detect standard and extended emojis
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed chars
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
    "\U00002600-\U000026FF"  # misc symbols
    "]+",
    flags=re.UNICODE,
)

TAGS_PATTERN = re.compile(
    r"\s*(\[|\()[^\]\)]*?(?:official|4k|1080p|720p|hd|full\s*hd|lyrics?|audio|teaser|trailer|60fps|remastered)[^\]\)]*?(\]|\))",
    re.IGNORECASE,
)

# Common Clickbait / Vlog / Video Phrase Rephrasing Rules
COMMON_PHRASE_REWRITES = [
    # Hindi/Hinglish Vlog & Drama patterns
    (r"(?i)\b(aaj\s+)?(ye\s+)?kya\s+ho\s+gaya\b", "Achanak Hua Ye Bada Hadsa"),
    (r"(?i)\b(aaj\s+)?subah\s+subah\b", "Subah Ke Waqt"),
    (r"(?i)\bkya\s+hua\s+mere\s+tabiyat\s+ka\b", "Meri Tabiyat Ka Asli Sach"),
    (r"(?i)\bvlogs?\s+kyun\s+nahi\s+aa\s+rahe\s+(hai)?\b", "Vlogs Na Aane Ki Badi Wajah"),
    (r"(?i)\bmain\s+vlog\s+kyon\s+nahi\s+bana\s+raha\s+hun\b", "Kyun Ruke Huye The Vlogs"),
    (r"(?i)\b(bohot|bahut)\s+badi\s+galti\s+kar\s+di(\s+maine)?\b", "Ho Gayi Mujhse Sabse Badi Bhool"),
    (r"(?i)\b(bohot|bahut)\s+dino\s+baad\b", "Kaafi Dino Ke Intezar Ke Baad"),
    (r"(?i)\byoutube\s+se\s+payment\s+aa\s+gaya\b", "YouTube First Earning & Payment Reveal"),
    (r"(?i)\bgood\s+news\s+for\s+(my\s+)?all\s+youtube\s+family\b", "Sabhi Ke Liye Ek Badi Good News"),
    (r"(?i)\bpehli\s+hi\s+video\s+viral\s+ho\s+gayi\b", "First Video Ho Gayi Super Viral"),
    (r"(?i)\bpura\s+fasal\s+barbaad\s+kar\s+diya\b", "Kisan Ka Bada Nuksan"),
    (r"(?i)\bwife\s+ne\s+bhuttha\s+jala\s+diya\b", "Kitchen Me Hungama - Bhutta Jal Gaya"),
    (r"(?i)\bdesi\s+style\s+fish\s+fry\b", "Crispy Desi Style Fish Fry Special"),
    (r"(?i)\bvideo\s+soot\s+karne\s+a(y|i)a\s+tha\b", "Video Shoot Ke Dauran"),

    # Devanagari Hindi phrases
    (r"बहुत बड़ी गलती कर दी मैंने", "मुझसे हो गई सबसे बड़ी भूल"),
    (r"क्या हो गया", "अचानक हुआ यह हादसा"),
    (r"पता चल गया कि मैं वीडियो बनाता हूँ", "सबके सामने आ गया मेरा यूट्यूब सच"),
    (r"सुबह सुबह", "मॉर्निंग के वक्त"),
    (r"बर्बाद कर दिया", "हुआ बहुत बड़ा नुकसान"),
    (r"क्यों नहीं आ रहे", "ना आने की असली वजह"),

    # English phrases
    (r"(?i)\bwhat\s+happened\s+this\s+morning\b", "Unexpected Morning Incident"),
    (r"(?i)\bdid\s+i\s+make\s+a\s+(huge|big)\s+mistake\b", "Was This My Biggest Mistake Ever?"),
    (r"(?i)\breceived\s+my\s+youtube\s+payment\b", "Revealing My YouTube Earnings"),
    (r"(?i)\beveryone\s+in\s+my\s+village\s+knows\b", "My Secret Revealed To The Whole Village"),
    (r"(?i)\bfirst\s+video\s+went\s+viral\b", "Going Viral On My Very First Video"),
]


def load_rules():
    """Load user title rewriting rules from title_rules.json."""
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                rules = dict(DEFAULT_RULES)
                rules.update(saved)
                return rules
        except Exception:
            pass
    return dict(DEFAULT_RULES)


def save_rules(rules):
    """Save title rewriting rules to title_rules.json."""
    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


def _clean_base_title(title, rules):
    """Initial cleaning: strip emojis, hashtags, mentions, and tags."""
    cleaned = title or ""

    if rules.get("remove_emojis", True):
        cleaned = EMOJI_PATTERN.sub("", cleaned)

    if rules.get("remove_hashtags", True):
        cleaned = re.sub(r"#\S+", "", cleaned)

    if rules.get("remove_mentions", True):
        cleaned = re.sub(r"@\S+", "", cleaned)

    if rules.get("remove_resolution_tags", True):
        cleaned = TAGS_PATTERN.sub("", cleaned)

    if rules.get("clean_separators", True):
        cleaned = re.sub(r"\s*\|\s*", " - ", cleaned)
        cleaned = re.sub(r"\s*//\s*", " - ", cleaned)
        cleaned = re.sub(r"\s*--+\s*", " - ", cleaned)

    cleaned = re.sub(r'[\\/:*?"<>|]', " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_.,")
    return cleaned


def _apply_semantic_rephrase(title):
    """Semantically rephrase common idioms, vlog patterns, and clickbait hooks."""
    t = title
    for pattern, replacement in COMMON_PHRASE_REWRITES:
        t = re.sub(pattern, replacement, t)

    # Clause restructuring: If title has "Part 1 - Part 2" or "A - B", rearrange clauses
    if " - " in t:
        parts = [p.strip() for p in t.split(" - ") if p.strip()]
        if len(parts) == 2:
            p1, p2 = parts[0], parts[1]
            # If part 2 is a descriptor (Vlog, Review, Day 1, etc.), place it as prefix
            if any(k in p2.lower() for k in ["vlog", "review", "part", "episode", "day", "update", "story"]):
                t = f"{p2}: {p1}"
            else:
                t = f"{p1} ({p2})"
        elif len(parts) > 2:
            t = f"{parts[0]} - {' '.join(parts[1:])}"

    return t


def _apply_hook_style(title, hook_style):
    """Add a catchy hook prefix or styling to the rewritten title."""
    if not hook_style or hook_style == "None":
        return title

    if hook_style == "Dramatic Hook":
        hooks = ["MUST WATCH", "UNEXPECTED", "SHOCKING", "SPECIAL EPISODE"]
        # Use simple hash of title to deterministically pick a hook
        idx = sum(ord(c) for c in title) % len(hooks)
        return f"{hooks[idx]}: {title}"
    elif hook_style == "Vlog Story":
        return f"Daily Life Vlog - {title}"
    elif hook_style == "Question Hook":
        if not title.endswith("?"):
            return f"Kya Sach Me {title}?"
        return title

    return title


def _ai_rewrite_gemini(title, api_key):
    """Rewrite title using Google Gemini REST API."""
    if not api_key:
        return _apply_semantic_rephrase(title)

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        prompt = (
            f"Rewrite this YouTube video title into a fresh, natural, engaging alternative title. "
            f"Keep the same language (Devanagari Hindi or Hinglish/English). "
            f"Do not include quotes or emojis. Return ONLY the new title.\nOriginal Title: {title}"
        )
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 60}
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode("utf-8"))
        candidate = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        candidate = candidate.strip('"\n\r. ')
        if candidate and len(candidate) > 3:
            return candidate
    except Exception:
        pass

    return _apply_semantic_rephrase(title)


def rewrite_title(title, rules=None):
    """Main rewrite entry point: transforms and rewrites title based on rules."""
    if not title:
        return "Video"

    if rules is None:
        rules = load_rules()

    # Step 1: Base cleaning
    clean_base = _clean_base_title(title, rules)

    # Step 2: Custom user replacements
    custom_reps = rules.get("custom_replacements", {})
    if isinstance(custom_reps, dict):
        for find_txt, repl_txt in custom_reps.items():
            if find_txt:
                clean_base = clean_base.replace(find_txt, repl_txt)

    mode = rules.get("rewrite_mode", "smart_rephrase")

    if mode == "clean_only":
        return clean_base or "Video"

    elif mode == "ai_gemini":
        gemini_key = rules.get("gemini_api_key", "").strip()
        rewritten = _ai_rewrite_gemini(clean_base, gemini_key)

    elif mode == "hook":
        rephrased = _apply_semantic_rephrase(clean_base)
        hook_style = rules.get("hook_style", "Dramatic Hook")
        rewritten = _apply_hook_style(rephrased, hook_style)

    elif mode == "reorder":
        if " - " in clean_base:
            parts = [p.strip() for p in clean_base.split(" - ") if p.strip()]
            rewritten = " - ".join(reversed(parts))
        else:
            rewritten = _apply_semantic_rephrase(clean_base)

    else:  # default 'smart_rephrase'
        rewritten = _apply_semantic_rephrase(clean_base)

    # Final cleanup of illegal filename characters
    rewritten = re.sub(r'[\\/:*?"<>|]', " ", rewritten)
    rewritten = re.sub(r"\s+", " ", rewritten).strip(" -_.,")

    return rewritten or clean_base or "Video"
