"""Analyse d'un fichier déposé (CR.5) : garde-fou A en code, puis modèle (simulé) ; il propose seulement."""

from __future__ import annotations

from kaldera.interface.lecteur import LecteurSimule, analyser


class LecteurEspion:
    """Compte les questions posées au modèle : une question, un appel (CR.5.3)."""

    def __init__(self) -> None:
        self.appels: list[str] = []

    def est_lisible(self, contenu: bytes) -> tuple[bool, str]:
        self.appels.append("lisibilite")
        return True, "ok"

    def lire_montant(self, contenu: bytes) -> float | None:
        self.appels.append("montant")
        return 12.5


def test_garde_fou_a_fichier_vide_le_modele_n_est_pas_appele() -> None:
    lecteur = LecteurEspion()
    r = analyser("facture", "f.pdf", b"", lecteur)
    assert r["lisible"] is False
    assert r["verdict"]["garde_fou"] == "A" and "vide" in r["verdict"]["raison"]
    assert lecteur.appels == []


def test_garde_fou_a_format_non_accepte() -> None:
    r = analyser("photo", "virus.exe", b"abc", LecteurEspion())
    assert r["lisible"] is False and r["verdict"]["garde_fou"] == "A"


def test_fichier_lisible_facture_deux_questions_distinctes() -> None:
    lecteur = LecteurEspion()
    r = analyser("facture", "f.pdf", b"contenu", lecteur)
    assert lecteur.appels == ["lisibilite", "montant"]
    assert r == {
        "lisible": True,
        "montant": 12.5,
        "verdict": {"garde_fou": "B", "raison": "ok"},
    }


def test_photo_pas_de_question_de_montant() -> None:
    lecteur = LecteurEspion()
    r = analyser("photo", "p.jpg", b"contenu", lecteur)
    assert lecteur.appels == ["lisibilite"] and "montant" not in r


def test_facture_illisible_pas_de_montant_propose() -> None:
    r = analyser("facture", "f.pdf", b"ILLISIBLE : tache", LecteurSimule())
    assert r["lisible"] is False and r["verdict"]["garde_fou"] == "B"
    assert "montant" not in r


def test_lecteur_simule_lit_le_montant_dans_le_texte() -> None:
    r = analyser("facture", "f.txt", "Facture\nMONTANT: 1 850,50".encode(), LecteurSimule())
    assert r["lisible"] is True and r["montant"] == 1850.5


def test_lecteur_simule_montant_introuvable_est_none() -> None:
    r = analyser("facture", "f.pdf", b"%PDF binaire sans marqueur", LecteurSimule())
    assert r["lisible"] is True and r["montant"] is None


def test_le_lecteur_simule_est_deterministe() -> None:
    contenu = b"MONTANT: 99"
    assert analyser("facture", "f.pdf", contenu, LecteurSimule()) == analyser(
        "facture", "f.pdf", contenu, LecteurSimule()
    )
