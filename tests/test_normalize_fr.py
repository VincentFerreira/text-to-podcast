import pytest

from podcast_gen.locales import get_locale
from podcast_gen.locales.fr.normalize import normalize


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("à 14h30", "à quatorze heures trente"),
        ("à 8 h et", "à huit heures et"),
        ("à 21h01", "à vingt et une heures une"),
        ("1h", "une heure"),
        ("3,5 %", "trois virgule cinq pour cent"),
        ("3,05 points", "trois virgule zéro cinq points"),
        ("1 250 000 €", "un million deux cent cinquante mille euros"),
        ("48 M€", "quarante-huit millions d'euros"),
        ("2,3 Md€", "deux virgule trois milliards d'euros"),
        ("-3 °C", "moins trois degrés"),
        ("le 04/10/2026", "le quatre octobre deux mille vingt-six"),
        ("le 1er mai", "le premier mai"),
        ("la 12e édition", "la douzième édition"),
        ("M. Dupont et Mme Martin", "Monsieur Dupont et Madame Martin"),
        ("70 km/h", "soixante-dix kilomètres heure"),
        ("**gras** et [lien](https://a.fr)", "gras et lien"),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_locale_registry():
    assert get_locale("fr").normalize_text("2 %") == "deux pour cent"
    with pytest.raises(ValueError):
        get_locale("xx")
