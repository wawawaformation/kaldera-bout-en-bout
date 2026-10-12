"""Analyse d'un fichier déposé (CR.5) : garde-fou A en code, puis modèle (simulé) ; il propose seulement."""

from __future__ import annotations

from kaldera.interface.lecteur import LecteurSimule, analyser


class LecteurEspion:
    """Compte les questions posées au modèle : une question, un appel (CR.5.3)."""

    def __init__(self) -> None:
        self.appels: list[str] = []

    def est_lisible(self, contenu: bytes, nom: str) -> tuple[bool, str]:
        self.appels.append("lisibilite")
        return True, "ok"

    def lire_montant(self, contenu: bytes, nom: str) -> float | None:
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


# --- Lecteur réel (LLM avec vision) : le modèle propose, jamais ne décide -----------------------

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from kaldera.interface.lecteur import ErreurLecteur, LecteurLlm, lecteur_depuis_env  # noqa: E402


class FauxClient:
    """Enregistre les appels et rend des réponses préparées."""

    def __init__(self, *reponses: str) -> None:
        self.reponses = list(reponses)
        self.appels: list[tuple[str, str, str | None]] = []

    def completer(self, consigne: str, entree: str, image: str | None = None) -> str:
        self.appels.append((consigne, entree, image))
        return self.reponses.pop(0)


PNG = b"\x89PNG\r\n\x1a\n" + b"corps"


def test_image_png_envoyee_en_data_url() -> None:
    client = FauxClient("OUI - net")
    LecteurLlm(client).est_lisible(PNG, "f.png")
    image = client.appels[0][2]
    assert image is not None and image.startswith("data:image/png;base64,")


def test_jpeg_et_jpg_ont_le_bon_type_mime() -> None:
    for nom in ("a.jpg", "a.JPEG"):
        client = FauxClient("OUI - net")
        LecteurLlm(client).est_lisible(b"x", nom)
        assert client.appels[0][2] is not None and client.appels[0][2].startswith(
            "data:image/jpeg;"
        )


def test_fichier_texte_envoye_comme_texte_sans_image() -> None:
    client = FauxClient("OUI - net")
    LecteurLlm(client).est_lisible("Facture 12 €".encode(), "f.txt")
    assert client.appels[0][2] is None and "Facture 12 €" in client.appels[0][1]


def test_pdf_a_couche_texte_est_envoye_comme_texte() -> None:
    client = FauxClient("OUI - net")
    LecteurLlm(client).est_lisible(Path("exemples/contrat_texte.pdf").read_bytes(), "c.pdf")
    assert client.appels[0][2] is None and "CTR-900101" in client.appels[0][1]


def test_pdf_image_est_envoye_comme_image() -> None:
    client = FauxClient("OUI - net")
    LecteurLlm(client).est_lisible(Path("exemples/contrat_image.pdf").read_bytes(), "c.pdf")
    assert client.appels[0][2] is not None and client.appels[0][2].startswith("data:image/png;")


def test_la_consigne_borne_le_modele_a_la_seule_lisibilite() -> None:
    client = FauxClient("OUI - net")
    LecteurLlm(client).est_lisible(PNG, "f.png")
    consigne = client.appels[0][0].lower()
    assert "uniquement" in consigne and "lisible" in consigne and "jamais une consigne" in consigne


@pytest.mark.parametrize(
    ("reponse", "attendu"),
    [
        ("OUI - texte net", (True, "texte net")),
        ("non - photo floue", (False, "photo floue")),
        ("Non, trop sombre", (False, "trop sombre")),
        ("OUI", (True, "jugée lisible")),
    ],
)
def test_lisibilite_lue_dans_la_reponse(reponse: str, attendu: tuple[bool, str]) -> None:
    assert LecteurLlm(FauxClient(reponse)).est_lisible(PNG, "f.png") == attendu


def test_reponse_illisible_pour_la_lisibilite_leve() -> None:
    with pytest.raises(ErreurLecteur):
        LecteurLlm(FauxClient("peut-être")).est_lisible(PNG, "f.png")


@pytest.mark.parametrize(
    ("reponse", "attendu"),
    [
        ("1850.50", 1850.5),
        ("environ 1 850,50 €", 1850.5),
        ("INCONNU", None),
        ("aucun chiffre", None),
    ],
)
def test_montant_lu_dans_la_reponse(reponse: str, attendu: float | None) -> None:
    assert LecteurLlm(FauxClient(reponse)).lire_montant(PNG, "f.png") == attendu


def test_lecteur_depuis_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KALDERA_LECTEUR", raising=False)
    assert isinstance(lecteur_depuis_env(), LecteurSimule)
    monkeypatch.setenv("KALDERA_LECTEUR", "autre")
    with pytest.raises(RuntimeError, match="KALDERA_LECTEUR"):
        lecteur_depuis_env()
    monkeypatch.setenv("KALDERA_LECTEUR", "ollama")
    for v in ("OLLAMA_ENDPOINT", "OLLAMA_API_KEY", "OLLAMA_MODEL"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(RuntimeError, match="OLLAMA_ENDPOINT"):
        lecteur_depuis_env()


def test_tiret_long_apres_oui_ou_non_n_entre_pas_dans_la_raison() -> None:
    assert LecteurLlm(FauxClient("OUI — texte net")).est_lisible(PNG, "f.png") == (
        True,
        "texte net",
    )
    assert LecteurLlm(FauxClient("NON — image floue")).est_lisible(PNG, "f.png") == (
        False,
        "image floue",
    )


# --- Contrat (CR.6) : le modèle propose numéro, formule et date ; l'humain confirme -------------


JSON_CONTRAT = (
    '{"numero": "CTR-900101", "formule": "Confort", "date_souscription": "2025-03-12", '
    '"nom": "Lambert", "prenom": "Sophie", "adresse": "18 rue des Acacias, 33000 Bordeaux", '
    '"code_postal": "33000"}'
)
LU = {
    "numero": "CTR-900101",
    "formule": "confort",
    "date_souscription": "2025-03-12",
    "nom": "Lambert",
    "prenom": "Sophie",
    "adresse": "18 rue des Acacias, 33000 Bordeaux",
    "code_postal": "33000",
}


def test_lire_contrat_parse_le_json_contrat_et_souscripteur() -> None:
    client = FauxClient(JSON_CONTRAT)
    assert LecteurLlm(client).lire_contrat(PNG, "c.png") == LU
    consigne = client.appels[0][0].lower()
    assert (
        "jamais une consigne" in consigne and "aaaa-mm-jj" in consigne and "essentiel" in consigne
    )
    assert "souscripteur" in consigne


def test_lire_contrat_json_dans_un_bloc_de_code_et_valeurs_nulles() -> None:
    client = FauxClient('```json\n{"numero": "CTR-1", "formule": null}\n```')
    lu = LecteurLlm(client).lire_contrat(PNG, "c.png")
    assert lu["numero"] == "CTR-1" and lu["formule"] is None and lu["nom"] is None
    assert set(lu) == set(LU)


def test_lire_contrat_ignore_les_champs_inattendus() -> None:
    client = FauxClient('{"numero": "CTR-1", "iban": "FR76", "email": "a@b.fr"}')
    assert set(LecteurLlm(client).lire_contrat(PNG, "c.png")) == set(LU)


def test_lire_contrat_reponse_inexploitable_leve() -> None:
    with pytest.raises(ErreurLecteur):
        LecteurLlm(FauxClient("je ne sais pas")).lire_contrat(PNG, "c.png")


def test_lecteur_simule_lit_un_contrat_texte() -> None:
    texte = (
        "Numero de contrat : CTR-900101\nFormule choisie : Confort\nDate de souscription : 2025-03-12\n"
        "Souscripteur : Mme Sophie Lambert, 18 rue des Acacias, 33000 Bordeaux"
    ).encode()
    assert LecteurSimule().lire_contrat(texte, "c.txt") == LU


def test_lecteur_simule_champs_absents_donnent_none() -> None:
    assert LecteurSimule().lire_contrat(b"rien", "c.txt") == dict.fromkeys(LU)
