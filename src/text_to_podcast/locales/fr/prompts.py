"""Prompts sent to the LLM that writes the show. In French: the model writes French."""

from __future__ import annotations

import re

# Leftovers small models add despite the rules, removed after generation
GREETING_RE = re.compile(
    r"^(re)?bonjour( à (tous|toutes)( et à tous)?| tout le monde)?\s*[,!.]*\s*", re.I
)
SIGNOFF_RE = re.compile(
    r"bonne (écoute|journée|soirée)|à (demain|bientôt|la semaine prochaine)", re.I
)

# Measured on the default voices (Piper siwis + Supertonic M3), pauses included
WORDS_PER_MINUTE = 160

TONES = {
    "dynamique": (
        "Ton de matinale radio : énergique, rythmé, chaleureux. Phrases courtes, relances vives, "
        "une pointe d'humour quand le sujet s'y prête."
    ),
    "posé": (
        "Ton posé et clair, comme un journal d'information : on prend le temps d'expliquer, "
        "sans précipitation ni familiarité."
    ),
    "décontracté": (
        "Ton décontracté de discussion entre collègues : tutoiement entre les animateurs, "
        "expressions du quotidien, réactions spontanées."
    ),
}

AUDIENCES = {
    "grand-public": (
        "Public grand public : pas de jargon sans explication, une image ou un exemple concret "
        "pour chaque notion technique, on dit pourquoi ça compte pour l'auditeur."
    ),
    "tech": (
        "Public de professionnels de la tech : on peut employer le vocabulaire technique, "
        "aller dans le détail, discuter des limites et des alternatives."
    ),
}

SYSTEM = (
    "Tu es l'auteur d'une matinale radio française présentée par {host} (la présentatrice, "
    "qui lance les sujets et relance) et {cohost} (le chroniqueur, qui explique et analyse). "
    "Tu écris en français naturel, à l'oral : phrases courtes, faciles à dire à voix haute. "
    "Tu ne dis que ce qui figure dans les sources : n'invente aucun chiffre, nom, date "
    "ou citation. "
    "Les sources peuvent être dans une autre langue : l'émission, elle, est toujours en français "
    "(garde en version originale les noms propres, sigles et termes techniques consacrés)."
)

OUTLINE = """Voici l'article dont on parle ce matin.

{source}

Découpe-le en {count} rubriques au maximum (au moins 2) : chacune traite un angle
différent de l'article, sans chevauchement, dans l'ordre logique de l'émission.
{brief}
Réponds uniquement avec un objet JSON de cette forme :
{{"title": "titre accrocheur de l'émission", "segments": [{{"title": "titre court (6 mots max)", "angle": "ce que la rubrique explique, en une phrase"}}]}}"""  # noqa: E501

SEGMENT = """Rubrique : « {title} »
Angle : {angle}

Sources de la rubrique :
{sources}

Rubriques déjà traitées dans l'émission (ne pas les répéter) : {done}

Écris l'échange entre {host} et {cohost} pour cette rubrique, environ {words} mots au total.
{tone}
{audience}
{brief}
Règles :
- une réplique par ligne, au format « {host} : texte » ou « {cohost} : texte » ;
- {turns} répliques au total, pas plus, en alternant les deux voix ; {host} ouvre la rubrique ;
- l'émission est déjà commencée : ni bonjour, ni au revoir, ni « bonne écoute » ;
- pas de titre, pas de didascalie, pas de Markdown ;
- uniquement ce qui est écrit dans les sources : aucun conseil pratique, chiffre, nom ou détail
  technique ajouté, même s'il te semble vrai."""

CONTINUE = """Voici le début de l'échange sur la rubrique « {title} » :

{dialogue}

Il est trop court. Continue l'échange avec environ {words} mots de plus, en approfondissant
un point des sources qui n'a pas encore été abordé. Même format : « {host} : texte » ou
« {cohost} : texte », une réplique par ligne, sans répéter ce qui a déjà été dit.

Sources :
{sources}"""
