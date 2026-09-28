"""Title Rewriter and Sanitizer Module for YouTube Video Downloader.
Cleans emojis, hashtags, channel mentions, resolution tags, and messy separators.
"""

import json
import os
import re

RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "title_rules.json")

DEFAULT_RULES = {
    "remove_emojis": True,
    "remove_hashtags": True,
    "remove_mentions": True,
    "remove_resolution_tags": True,
    "clean_separators": True,
    "trim_junk": True,
    "custom_replacements": {},  # e.g. {"old_word": "new_word"}
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
    "\U00002600-\U000026FF"  # misc symbols (☀, ☕, etc.)
    "]+",
    flags=re.UNICODE,
)

# Resolution & tag pattern (e.g., [Official Video], (4K), [1080p], (Lyric Video), etc.)
TAGS_PATTERN = re.compile(
    r"\s*(\[|\()[^\]\)]*?(?:official|4k|1080p|720p|hd|full\s*hd|lyrics?|audio|teaser|trailer|60fps|remastered)[^\]\)]*?(\]|\))",
    re.IGNORECASE,
)


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


def rewrite_title(title, rules=None):
    """Rewrite and clean a video title based on configured rules."""
    if not title:
        return "Video"

    if rules is None:
        rules = load_rules()

    cleaned = title

    # 1. Custom replacements first
    custom_reps = rules.get("custom_replacements", {})
    if isinstance(custom_reps, dict):
        for find_txt, repl_txt in custom_reps.items():
            if find_txt:
                cleaned = cleaned.replace(find_txt, repl_txt)

    # 2. Remove Emojis
    if rules.get("remove_emojis", True):
        cleaned = EMOJI_PATTERN.sub("", cleaned)

    # 3. Remove Hashtags (#shorts, #vlog, #viral, etc.)
    if rules.get("remove_hashtags", True):
        cleaned = re.sub(r"#\S+", "", cleaned)

    # 4. Remove Channel Mentions (@channelname)
    if rules.get("remove_mentions", True):
        cleaned = re.sub(r"@\S+", "", cleaned)

    # 5. Remove Resolution / Video Tags like [1080p], (Official Video)
    if rules.get("remove_resolution_tags", True):
        cleaned = TAGS_PATTERN.sub("", cleaned)

    # 6. Clean and normalize separators (| -> - , // -> - , repeated dashes)
    if rules.get("clean_separators", True):
        cleaned = re.sub(r"\s*\|\s*", " - ", cleaned)
        cleaned = re.sub(r"\s*//\s*", " - ", cleaned)
        cleaned = re.sub(r"\s*--+\s*", " - ", cleaned)

    # 7. Trim whitespace, dangling hyphens, and illegal characters
    cleaned = re.sub(r'[\\/:*?"<>|]', " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_.,")

    # Fallback if empty after stripping
    if not cleaned:
        cleaned = "Cleaned_Video"

    return cleaned
