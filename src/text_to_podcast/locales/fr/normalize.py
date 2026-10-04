"""French text normalization before speech synthesis.

TTS models read digits, symbols and abbreviations poorly, so they are spelled
out as words first (e.g. "14h30" -> "quatorze heures trente").
"""

from __future__ import annotations

import re

from num2words import num2words

MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]  # fmt: skip

# Thousands separators: regular space, no-break space, narrow no-break space
_SPACES = "   "

ABBREVIATIONS = [
    (r"\bMM\.\s", "Messieurs "),
    (r"\bM\.\s(?=[A-ZÉÈ])", "Monsieur "),
    (r"\bMmes\b\.?", "Mesdames"),
    (r"\bMme\b\.?", "Madame"),
    (r"\bMlle\b\.?", "Mademoiselle"),
    (r"\bDr\b\.?", "docteur"),
    (r"\bPr\b\.?(?=\s[A-ZÉÈ])", "professeur"),
    (r"\bSte\b\.?(?=[\s-])", "Sainte"),
    (r"\bSt\b\.?(?=[\s-])", "Saint"),
    (r"\betc\.", "et cetera."),
    (r"\bcf\.", "voir"),
    (r"\bn°\s*", "numéro "),
    (r"\bkm/h\b", "kilomètres heure"),
    (r"\bkm²", "kilomètres carrés"),
    (r"\bm²", "mètres carrés"),
    (r"\bkm\b", "kilomètres"),
    (r"\bkg\b", "kilos"),
    (r"\bMds?\b", "milliards"),
    (r"\bmds?\b", "milliards"),
    (r"\bmln\b", "millions"),
    (r"&", " et "),
]

CURRENCIES = [
    (r"M€|millions? d'euros", "millions d'euros"),
    (r"Md€|Mds?€|milliards? d'euros", "milliards d'euros"),
    (r"€|euros?", "euros"),
    (r"\$|dollars?", "dollars"),
    (r"£", "livres"),
]

_NUM = rf"\d{{1,3}}(?:[{_SPACES}]\d{{3}})+(?:[,.]\d+)?|\d+(?:[,.]\d+)?"


def number_to_words(raw: str) -> str:
    """'1 250' -> 'mille deux cent cinquante', '3,05' -> 'trois virgule zéro cinq'."""
    raw = re.sub(f"[{_SPACES}]", "", raw).replace(".", ",")
    if "," in raw:
        whole, dec = raw.split(",", 1)
        # Leading zeros of the decimal part are spoken
        zeros = " ".join("zéro" for _ in range(len(dec) - len(dec.lstrip("0"))))
        rest = dec.lstrip("0")
        rest_words = num2words(int(rest), lang="fr") if rest else ""
        dec_words = " ".join(w for w in (zeros, rest_words) if w)
        return f"{num2words(int(whole or 0), lang='fr')} virgule {dec_words}"
    return num2words(int(raw), lang="fr")


def _feminine(words: str) -> str:
    """'vingt et un' -> 'vingt et une' ("heure" and "minute" are feminine)."""
    return re.sub(r"\bun$", "une", words)


def _time(m: re.Match) -> str:
    hours = _feminine(number_to_words(m.group(1)))
    unit = "heure" if int(m.group(1)) <= 1 else "heures"
    minutes = m.group(2)
    if minutes and int(minutes):
        return f"{hours} {unit} {_feminine(number_to_words(minutes))}"
    return f"{hours} {unit}"


def _date(m: re.Match) -> str:
    day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return m.group(0)
    if len(year) == 2:
        year = "20" + year
    day_words = "premier" if day == 1 else num2words(day, lang="fr")
    return f"{day_words} {MONTHS[month - 1]} {num2words(int(year), lang='fr')}"


def _ordinal(m: re.Match) -> str:
    n, suffix = int(m.group(1)), m.group(2).lower()
    if n == 1:
        return "première" if suffix in ("re", "ère") else "premier"
    return num2words(n, lang="fr", to="ordinal")


def clean_markup(text: str) -> str:
    """Strip Markdown and URLs, normalize typography."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [link](url) -> link
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"^\s*[-+•]\s+", "", text, flags=re.M)  # bullets
    text = text.replace("« ", "« ").replace(" »", " »")
    text = re.sub(r"[«»“”„]", '"', text)
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"\s*[–—]\s*", ", ", text)  # dashes -> commas (natural pause)
    return text


def normalize(text: str) -> str:
    """Turn French text into something a TTS model can read aloud."""
    text = clean_markup(text)

    # Dates DD/MM/YYYY
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b", _date, text)
    # Times: 14h30, 8 h, 21H05
    text = re.sub(r"\b(\d{1,2})\s?[hH](?:\s?(\d{2}))?\b", _time, text)
    # Ordinals: 1er, 1re, 2e, 3ème, 21es
    text = re.sub(r"\b(\d+)(er|re|ère|e|ème|es|èmes)\b", _ordinal, text)
    # Percentages
    text = re.sub(rf"({_NUM})\s?%", lambda m: f"{number_to_words(m.group(1))} pour cent", text)
    # Temperatures
    text = re.sub(
        rf"(-?)({_NUM})\s?°C?",
        lambda m: f"{'moins ' if m.group(1) else ''}{number_to_words(m.group(2))} degrés",
        text,
    )
    # Amounts of money
    for symbol, words in CURRENCIES:
        text = re.sub(
            rf"({_NUM})\s?(?:{symbol})(?![\w])",
            lambda m, w=words: f"{number_to_words(m.group(1))} {w}",
            text,
        )
    # Remaining numbers
    text = re.sub(rf"(?<![\w,]){_NUM}(?![\w])", lambda m: number_to_words(m.group(0)), text)
    # After amounts, so that "Md€" is handled as a currency
    for pattern, repl in ABBREVIATIONS:
        text = re.sub(pattern, repl, text)

    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([!?;:])(?=\S)", r"\1 ", text)
    return re.sub(r"\s+", " ", text).strip()
