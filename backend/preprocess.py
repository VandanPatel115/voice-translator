import re
import json
from pathlib import Path

HESITATIONS = re.compile(
    r"\b(?:uh+|um+|uhm+|erm*|hmm+|ah+)\b[,.]?\s*",
    flags=re.IGNORECASE,
)


def clean_fillers(text: str) -> str:
    """Remove hesitation sounds like 'uh' and 'um'. Leaves meaningful words alone."""
    text = HESITATIONS.sub("", text)
    text = re.sub(r"\s{2,}", " ", text)           # collapse double spaces
    text = re.sub(r"^[\s,.]+", "", text)          # drop leading commas/dots
    return text.strip()

GLOSSARY = json.loads(Path(__file__).with_name("glossary.json").read_text())
KEEP_ENGLISH = sorted(GLOSSARY["keep_english"], key=len, reverse=True)

EXPANSIONS = GLOSSARY.get("expand", {})


def expand_abbreviations(text: str) -> str:
    """Replace abbreviations like ETA with their full words."""
    for short, full in EXPANSIONS.items():
        text = re.sub(rf"\b{re.escape(short)}\b", full, text)
    return text

def protect(text: str) -> tuple[str, dict[str, str]]:
    """Replace glossary names with tokens like ⟦0⟧. Returns the new text and a token map."""
    mapping: dict[str, str] = {}
    for term in KEEP_ENGLISH:
        pattern = re.compile(rf"\b{re.escape(term)}\b", flags=re.IGNORECASE)
        if pattern.search(text):
            token = f"⟦{len(mapping)}⟧"
            text = pattern.sub(token, text)
            mapping[token] = term
    return text, mapping


def restore(hindi: str, mapping: dict[str, str]) -> str | None:
    """Put names back. Returns None if any token went missing."""
    for token, term in mapping.items():
        if token not in hindi:
            return None
        hindi = hindi.replace(token, term)
    return hindi

if __name__ == "__main__":
    tests = [
        "Uh, so, um, can you send me the file?",
        "Hmm. I think, uh, we should go.",
        "Bring an umbrella and some hummus.",
        "Um... uh...",
    ]
    for t in tests:
        print(f"{t!r:45} → {clean_fillers(t)!r}")