"""Everything the hosts say that is not part of the input text, in French."""

from __future__ import annotations

import datetime as dt

from num2words import num2words

from .normalize import MONTHS

DEFAULT_SHOW = "votre édition du matin"

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

TRANSITIONS = [
    "Autre sujet ce matin.",
    "On poursuit avec l'actualité.",
    "Passons à présent à un autre sujet.",
    "Restons attentifs à cette autre information.",
]
LAST_TRANSITION = "Enfin."

HANDOFFS = [
    "{cohost}, vous suivez ce dossier.",
    "{cohost}, c'est vous qui nous en parlez.",
    "On retrouve {cohost} sur ce sujet.",
]


def spoken_date(day: dt.date) -> str:
    """dt.date(2026, 10, 4) -> 'dimanche quatre octobre deux mille vingt-six'."""
    num = "premier" if day.day == 1 else num2words(day.day, lang="fr")
    month = MONTHS[day.month - 1]
    return f"{DAYS[day.weekday()]} {num} {month} {num2words(day.year, lang='fr')}"


def transition(index: int, last: bool = False) -> str:
    return LAST_TRANSITION if last else TRANSITIONS[index % len(TRANSITIONS)]


def contents(titles: list[str]) -> str:
    """Table of contents announced after the intro."""
    listing = ", ".join(titles[:-1]) + (", et " if len(titles) > 2 else " et ") + titles[-1]
    return f"Au sommaire ce matin : {listing}."


# Single-voice edition


def solo_intro(day: dt.date, show: str) -> str:
    return f"Bonjour, nous sommes le {spoken_date(day)}. Voici {show}."


def solo_outro(show: str) -> str:
    return f"C'était {show}. Merci de nous avoir écoutés, et excellente journée à toutes et à tous."


# Two-voice edition


def dialogue_intro(day: dt.date, show: str, host: str, cohost: str) -> tuple[str, str]:
    """(host line, cohost reply)."""
    return (
        f"Bonjour, nous sommes le {spoken_date(day)}. Bienvenue dans {show}. "
        f"Je suis {host}, et à mes côtés ce matin, {cohost}.",
        f"Bonjour {host}, bonjour à toutes et à tous.",
    )


def handoff(index: int, cohost: str) -> str:
    return HANDOFFS[index % len(HANDOFFS)].format(cohost=cohost)


def thanks(name: str) -> str:
    return f"Merci {name}."


def dialogue_outro(show: str, host: str, cohost: str, thank_cohost: bool) -> list[tuple[str, str]]:
    """Closing lines as (role, text) pairs, role being "host" or "cohost"."""
    lead = f"{thanks(cohost)} " if thank_cohost else ""
    return [
        ("host", f"{lead}C'est la fin de {show}."),
        ("cohost", f"{thanks(host)} Excellente journée à toutes et à tous."),
        ("host", "Et à demain."),
    ]


def episode_title(day: dt.date) -> str:
    """Metadata title used when the input has no `# Title`."""
    return f"Édition du {day.isoformat()}"
