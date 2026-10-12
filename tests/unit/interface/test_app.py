"""API et page du démonstrateur : la couche devant le moteur (conception C-R)."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kaldera.interface.app import creer_app
from kaldera.interface.stockage import Stockage


def fichier(texte: str, nom: str = "f.txt") -> dict[str, str]:
    return {"nom": nom, "contenu": base64.b64encode(texte.encode()).decode()}


FACTURE = {"type": "facture", "fichier": fichier("Facture plomberie\nMONTANT: 1850")}
PHOTO = {"type": "photo", "fichier": fichier("photo du dégât")}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    Stockage(tmp_path).amorcer(Path("eval/scenarios.jsonl"))
    return TestClient(creer_app(tmp_path))


def saisie(**plus: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "numero_contrat": "CTR-778801",
        "sinistre": {
            "type": "degat_des_eaux",
            "date_survenance": "2026-08-14",
            "date_declaration": "2026-08-18",
            "montant_declare": 1850.0,
            "description": "Fuite",
        },
        "pieces": [FACTURE, PHOTO],
    }
    base.update(plus)
    return base


def test_la_page_d_accueil_est_servie(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200 and "<form" in r.text


def test_liste_des_contrats(client: TestClient) -> None:
    assert "CTR-778801" in client.get("/api/contrats").json()


def test_l_assure_se_deduit_du_contrat(client: TestClient) -> None:
    demande = client.post("/api/demandes", json=saisie()).json()["demande"]
    assert demande["assure"]["id_client"] == "CL-10021"  # CTR-778801 est rattaché à CL-10021


def test_soumission_valide_rend_la_fiche_et_sauvegarde_la_demande(client: TestClient) -> None:
    r = client.post("/api/demandes", json=saisie())
    assert r.status_code == 200
    fiche = r.json()["fiche"]
    assert (fiche["issue"], fiche["decision"], fiche["montant_rembourse"]) == (
        "decision",
        "acceptee",
        1700.0,
    )
    reference = r.json()["demande"]["reference"]
    assert re.fullmatch(r"KAL-\d{2}-0001", reference)  # première demande : numéro 0001
    assert client.get(f"/api/demandes/{reference}").json()["reference"] == reference
    assert reference in client.get("/api/demandes").json()


def test_saisie_invalide_renvoie_422_sans_appeler_le_moteur(client: TestClient) -> None:
    r = client.post("/api/demandes", json=saisie(numero_contrat=""))
    assert r.status_code == 422 and r.json()["erreurs"]
    assert client.get("/api/demandes").json() == []


def test_contrat_introuvable_422(client: TestClient) -> None:
    assert client.post("/api/demandes", json=saisie(numero_contrat="X")).status_code == 422


def test_dossier_incomplet_sans_depot_est_escalade_pieces_manquantes(client: TestClient) -> None:
    s = saisie(pieces=[FACTURE])
    fiche = client.post("/api/demandes", json=s).json()["fiche"]
    assert (fiche["issue"], fiche["file"]) == ("escalade", "gestionnaire")
    assert "pièces manquantes" in fiche["motif"].lower()


def test_des_depots_envoyes_quand_meme_ne_sont_pas_transmis_au_moteur(client: TestClient) -> None:
    s = saisie(pieces=[FACTURE], depots=[{"type": "photo", "lisible": True}])
    demande = client.post("/api/demandes", json=s).json()["demande"]
    assert demande["espace_assure"] == {"depots": []}


def test_rejeu_d_une_demande_sauvegardee(client: TestClient) -> None:
    r = client.post("/api/demandes", json=saisie()).json()
    premiere = r["fiche"]
    rejeu = client.post(f"/api/demandes/{r['demande']['reference']}/rejouer").json()
    # un rejeu est un nouveau dossier (le partenaire n'accepte qu'un appel par référence)
    assert rejeu["demande"]["reference"] != r["demande"]["reference"]
    assert client.get(f"/api/demandes/{rejeu['demande']['reference']}").status_code == 200
    ignores = {"trace", "reference"}
    assert {k: v for k, v in rejeu["fiche"].items() if k not in ignores} == {
        k: v for k, v in premiere.items() if k not in ignores
    }


def test_demande_inconnue_404(client: TestClient) -> None:
    assert client.get("/api/demandes/KAL-26-0000").status_code == 404
    assert client.post("/api/demandes/KAL-26-0000/rejouer").status_code == 404


def test_reference_avec_chemin_n_echappe_pas_au_dossier(client: TestClient) -> None:
    assert client.get("/api/demandes/..%2Fassures%2FCL-10021").status_code == 404


def test_analyse_d_un_fichier_propose_sans_rien_decider(client: TestClient) -> None:
    import base64

    contenu = base64.b64encode(b"Facture\nMONTANT: 1850").decode()
    r = client.post(
        "/api/pieces/analyser", json={"type": "facture", "nom": "f.txt", "contenu": contenu}
    )
    assert r.status_code == 200
    assert r.json()["montant"] == 1850.0 and r.json()["lisible"] is True
    assert client.get("/api/demandes").json() == []


def test_analyse_contenu_non_base64_422(client: TestClient) -> None:
    r = client.post("/api/pieces/analyser", json={"type": "photo", "nom": "p.jpg", "contenu": "%%"})
    assert r.status_code == 422


def test_la_demande_porte_ce_que_le_serveur_a_lu_avec_son_verdict(client: TestClient) -> None:
    demande = client.post("/api/demandes", json=saisie()).json()["demande"]
    facture, photo = demande["pieces"]
    assert (facture["lisible"], facture["montant"], facture["verdict"]["garde_fou"]) == (
        True,
        1850.0,
        "B",
    )
    assert photo["lisible"] is True and "montant" not in photo and "fichier" not in facture


def test_le_serveur_ignore_ce_que_le_navigateur_declare_sur_une_piece(client: TestClient) -> None:
    """On ne fait jamais confiance au front-end : lisibilité, montant et verdict sont relus."""
    truquee = {
        "type": "facture",
        "lisible": True,
        "montant": 99999.0,
        "verdict": {"garde_fou": "B", "raison": "tout va bien"},
        "fichier": fichier("ILLISIBLE\nMONTANT: 1850"),
    }
    demande = client.post("/api/demandes", json=saisie(pieces=[truquee, PHOTO])).json()["demande"]
    piece = demande["pieces"][0]
    assert piece["lisible"] is False and "montant" not in piece
    assert "99999" not in repr(demande) and piece["verdict"]["raison"] != "tout va bien"


def test_le_montant_lu_sur_la_facture_l_emporte_sur_celui_du_navigateur(client: TestClient) -> None:
    facture = {**FACTURE, "montant": 1.0}
    pieces = client.post("/api/demandes", json=saisie(pieces=[facture, PHOTO])).json()["demande"][
        "pieces"
    ]
    assert pieces[0]["montant"] == 1850.0


def test_montant_non_lu_le_montant_saisi_sert_sinon_422(client: TestClient) -> None:
    sans_chiffre = {"type": "facture", "fichier": fichier("Facture sans total lisible")}
    r = client.post(
        "/api/demandes", json=saisie(pieces=[{**sans_chiffre, "montant": 1850.0}, PHOTO])
    )
    assert r.status_code == 200 and r.json()["demande"]["pieces"][0]["montant"] == 1850.0
    r = client.post("/api/demandes", json=saisie(pieces=[sans_chiffre, PHOTO]))
    assert r.status_code == 422 and "montant" in r.json()["erreurs"][0]


@pytest.mark.parametrize(
    "piece",
    [
        {"type": "facture", "lisible": True, "montant": 1850.0},  # déclarative, sans fichier
        {"type": "photo"},
        {"type": "selfie", "fichier": fichier("x")},
        {"type": "photo", "fichier": {"nom": "p.jpg", "contenu": "%%"}},
    ],
)
def test_une_piece_sans_fichier_ou_invalide_est_refusee(
    client: TestClient, piece: dict[str, Any]
) -> None:
    r = client.post("/api/demandes", json=saisie(pieces=[piece]))
    assert r.status_code == 422 and r.json()["erreurs"]
    assert client.get("/api/demandes").json() == []


def test_lecteur_indisponible_la_soumission_est_refusee_sans_rien_enregistrer(
    tmp_path: Path,
) -> None:
    from kaldera.interface.lecteur import ErreurLecteur

    class Casse:
        def est_lisible(self, contenu: bytes, nom: str) -> tuple[bool, str]:
            raise ErreurLecteur("PDF non pris en charge")

        def lire_montant(self, contenu: bytes, nom: str) -> float | None:
            raise ErreurLecteur("x")

    Stockage(tmp_path).amorcer(Path("eval/scenarios.jsonl"))
    c = TestClient(creer_app(tmp_path, lecteur=Casse()))  # type: ignore[arg-type]
    contenu = base64.b64encode(b"%PDF-1.4").decode()
    r = c.post("/api/pieces/analyser", json={"type": "facture", "nom": "f.pdf", "contenu": contenu})
    assert r.status_code == 503 and "PDF" in r.json()["erreurs"][0]
    r = c.post("/api/demandes", json=saisie())
    assert r.status_code == 503 and "PDF" in r.json()["erreurs"][0]
    assert c.get("/api/demandes").json() == []  # aucune demande, aucun numéro consommé


# --- Enregistrement d'un contrat depuis un fichier (CR.6) : le scan fournit aussi l'assuré ------

CONTRAT_TEXTE = (
    "Numero de contrat : CTR-900101\nFormule choisie : Confort\nDate de souscription : 2025-03-12\n"
    "Souscripteur : Mme Sophie Lambert, 18 rue des Acacias, 33000 Bordeaux"
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


def corps_contrat(**plus: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "numero": "CTR-900101",
        "formule": "confort",
        "date_souscription": "2025-03-12",
        "statut": "actif",
        "cotisations_a_jour": True,
        "assure": {
            "nom": "Lambert",
            "prenom": "Sophie",
            "adresse": "18 rue des Acacias, 33000 Bordeaux",
            "code_postal": "33000",
            "email": "s.lambert@example.org",
            "telephone": "",
            "iban": "",
        },
        "proposition": dict(LU),
        "fichier": {"nom": "c.txt", "contenu": base64.b64encode(CONTRAT_TEXTE.encode()).decode()},
    }
    base.update(plus)
    return base


def test_analyse_d_un_contrat_propose_contrat_et_souscripteur_sans_rien_stocker(
    client: TestClient,
) -> None:
    contenu = base64.b64encode(CONTRAT_TEXTE.encode()).decode()
    r = client.post("/api/contrats/analyser", json={"nom": "c.txt", "contenu": contenu})
    assert r.status_code == 200 and r.json() == LU
    assert "CTR-900101" not in client.get("/api/contrats").json()


def test_analyse_de_contrat_impossible_503_saisie_manuelle(tmp_path: Path) -> None:
    from kaldera.interface.lecteur import ErreurLecteur

    class Casse:
        def lire_contrat(self, contenu: bytes, nom: str) -> dict[str, Any]:
            raise ErreurLecteur("PDF illisible")

    c = TestClient(creer_app(tmp_path, lecteur=Casse()))  # type: ignore[arg-type]
    r = c.post(
        "/api/contrats/analyser", json={"nom": "c.pdf", "contenu": base64.b64encode(b"x").decode()}
    )
    assert r.status_code == 503 and "saisir à la main" in r.json()["erreurs"][0]


def test_enregistrement_confirme_sans_correction_tout_vient_du_modele(client: TestClient) -> None:
    r = client.post("/api/contrats", json=corps_contrat())
    assert r.status_code == 200
    assert set(r.json()["origines"]) == set(LU) and set(r.json()["origines"].values()) == {"modele"}
    assert "CTR-900101" in client.get("/api/contrats").json()


def test_un_champ_reconnu_par_le_modele_ne_peut_pas_etre_modifie(client: TestClient) -> None:
    r = client.post("/api/contrats", json=corps_contrat(formule="premium"))
    assert r.status_code == 422 and "non modifiable" in " ".join(r.json()["erreurs"])
    corps = corps_contrat()
    corps["assure"]["nom"] = "Martin"
    assert client.post("/api/contrats", json=corps).status_code == 422
    assert "CTR-900101" not in client.get("/api/contrats").json()


def test_la_proposition_renvoyee_par_le_navigateur_est_ignoree(client: TestClient) -> None:
    """On ne fait jamais confiance au front-end : le serveur relit le fichier lui-même."""
    corps = corps_contrat(formule="premium")
    corps["proposition"]["formule"] = "premium"  # le client prétend que le modèle a lu « premium »
    assert client.post("/api/contrats", json=corps).status_code == 422  # le fichier dit « confort »


def test_un_champ_non_reconnu_se_saisit_et_est_trace_humain(client: TestClient) -> None:
    corps = corps_contrat()
    sans_formule = CONTRAT_TEXTE.replace("Formule choisie : Confort\n", "")
    corps["fichier"] = {"nom": "c.txt", "contenu": base64.b64encode(sans_formule.encode()).decode()}
    r = client.post("/api/contrats", json=corps)
    assert r.status_code == 200
    assert (
        r.json()["origines"]["formule"] == "humain" and r.json()["origines"]["numero"] == "modele"
    )


def test_lecteur_de_contrat_en_panne_la_saisie_manuelle_reste_possible(tmp_path: Path) -> None:
    from kaldera.interface.lecteur import ErreurLecteur

    class Casse:
        def lire_contrat(self, contenu: bytes, nom: str) -> dict[str, Any]:
            raise ErreurLecteur("service en panne")

    c = TestClient(creer_app(tmp_path, lecteur=Casse()))  # type: ignore[arg-type]
    r = c.post("/api/contrats", json=corps_contrat())
    assert r.status_code == 200 and set(r.json()["origines"].values()) == {"humain"}


def test_contrat_saisi_sans_proposition_tout_est_humain(client: TestClient) -> None:
    corps = corps_contrat()
    del corps["proposition"], corps["fichier"]
    r = client.post("/api/contrats", json=corps)
    assert r.status_code == 200 and set(r.json()["origines"].values()) == {"humain"}


def test_l_assure_est_cree_avec_un_identifiant_genere_et_rattache_au_contrat(
    client: TestClient,
) -> None:
    r = client.post("/api/contrats", json=corps_contrat()).json()
    id_client = r["assure"]["id_client"]
    assert id_client.startswith("CL-") and r["assure"]["nom"] == "Lambert"
    assert id_client not in {"CL-10021", "CL-10388"}  # nouvel assuré, pas un assuré des scénarios
    demande = client.post("/api/demandes", json=saisie(numero_contrat="CTR-900101")).json()[
        "demande"
    ]
    assert demande["assure"]["id_client"] == id_client
    assert (
        demande["assure"]["code_postal"] == "33000"
        and demande["assure"]["email"] == "s.lambert@example.org"
    )


def test_reenregistrer_le_meme_contrat_garde_le_meme_assure(client: TestClient) -> None:
    premier = client.post("/api/contrats", json=corps_contrat()).json()["assure"]["id_client"]
    corps = corps_contrat(statut="suspendu")
    second = client.post("/api/contrats", json=corps).json()["assure"]["id_client"]
    assert premier == second


def test_contrat_ou_assure_invalide_422_rien_n_est_stocke(client: TestClient) -> None:
    corps = corps_contrat(formule="luxe", date_souscription="demain")
    del corps["proposition"], corps["fichier"]  # saisi à la main : seul le contrôle de forme s'applique
    corps["assure"]["code_postal"] = "12"
    r = client.post("/api/contrats", json=corps)
    assert r.status_code == 422 and len(r.json()["erreurs"]) == 3
    assert "CTR-900101" not in client.get("/api/contrats").json()


def test_une_demande_n_a_que_les_cinq_champs_du_contrat(client: TestClient) -> None:
    client.post("/api/contrats", json=corps_contrat())
    r = client.post("/api/demandes", json=saisie(numero_contrat="CTR-900101"))
    assert r.status_code == 200
    assert set(r.json()["demande"]["contrat"]) == {
        "numero",
        "formule",
        "date_souscription",
        "statut",
        "cotisations_a_jour",
    }


def test_les_sinistres_recents_viennent_de_la_saisie(client: TestClient) -> None:
    demande = client.post("/api/demandes", json=saisie(sinistres_12_mois=4)).json()["demande"]
    assert demande["historique"] == {"sinistres_12_mois": 4}


def test_les_references_sont_generees_et_croissantes(client: TestClient) -> None:
    refs = [
        client.post("/api/demandes", json=saisie()).json()["demande"]["reference"] for _ in range(3)
    ]
    numeros = [int(r.rsplit("-", 1)[1]) for r in refs]
    assert numeros == [1, 2, 3] and len(set(refs)) == 3


def test_une_saisie_refusee_ne_consomme_pas_de_numero(client: TestClient) -> None:
    assert client.post("/api/demandes", json=saisie(numero_contrat="")).status_code == 422
    assert (
        client.post("/api/demandes", json=saisie()).json()["demande"]["reference"].endswith("-0001")
    )


def test_une_reference_envoyee_par_le_client_est_ignoree(client: TestClient) -> None:
    ref = client.post("/api/demandes", json=saisie(reference="KAL-26-4242")).json()["demande"][
        "reference"
    ]
    assert not ref.endswith("-4242")


# --- Bout de chaîne : la lettre au client et le bouton « Envoyer » (sans e-mail) ----------------


def soumettre(client: TestClient, **plus: Any) -> str:
    return client.post("/api/demandes", json=saisie(**plus)).json()["demande"]["reference"]


def test_la_lettre_est_redigee_depuis_la_fiche_du_dossier(client: TestClient) -> None:
    ref = soumettre(client)
    r = client.post(f"/api/demandes/{ref}/courrier")
    assert r.status_code == 200
    c = r.json()
    assert ref in c["texte"] and "1 700,00 €" in c["texte"] and c["origine"] == "standard"
    assert c["envoye_le"] is None and c["canal"] == "aucun e-mail (simulation)"
    assert client.get(f"/api/demandes/{ref}/courrier").json()["texte"] == c["texte"]


def test_lettre_d_un_dossier_escalade_ne_dit_rien_de_la_fraude(client: TestClient) -> None:
    ref = soumettre(client, pieces=[FACTURE])
    texte = client.post(f"/api/demandes/{ref}/courrier").json()["texte"].lower()
    assert "pièces" in texte and "fraude" not in texte and "vigilance" not in texte


def test_envoyer_marque_la_lettre_envoyee_sans_envoyer_d_e_mail(client: TestClient) -> None:
    ref = soumettre(client)
    client.post(f"/api/demandes/{ref}/courrier")
    r = client.post(f"/api/demandes/{ref}/courrier/envoyer")
    assert r.status_code == 200 and re.fullmatch(r"20\d\d-\d\d-\d\dT.*", r.json()["envoye_le"])
    assert client.get(f"/api/demandes/{ref}/courrier").json()["envoye_le"] == r.json()["envoye_le"]


def test_double_envoi_refuse(client: TestClient) -> None:
    ref = soumettre(client)
    client.post(f"/api/demandes/{ref}/courrier")
    client.post(f"/api/demandes/{ref}/courrier/envoyer")
    assert client.post(f"/api/demandes/{ref}/courrier/envoyer").status_code == 409


def test_une_lettre_envoyee_n_est_plus_regeneree(client: TestClient) -> None:
    ref = soumettre(client)
    premiere = client.post(f"/api/demandes/{ref}/courrier").json()
    envoyee = client.post(f"/api/demandes/{ref}/courrier/envoyer").json()
    encore = client.post(f"/api/demandes/{ref}/courrier").json()
    assert encore["texte"] == premiere["texte"] and encore["envoye_le"] == envoyee["envoye_le"]


def test_envoyer_sans_lettre_404_et_dossier_inconnu_404(client: TestClient) -> None:
    ref = soumettre(client)
    assert client.post(f"/api/demandes/{ref}/courrier/envoyer").status_code == 404
    assert client.post("/api/demandes/KAL-26-4242/courrier").status_code == 404
    assert client.get("/api/demandes/KAL-26-4242/courrier").status_code == 404


def test_la_lettre_d_un_rejeu_utilise_la_fiche_du_nouveau_dossier(client: TestClient) -> None:
    ref = soumettre(client)
    nouvelle = client.post(f"/api/demandes/{ref}/rejouer").json()["demande"]["reference"]
    assert "1 700,00 €" in client.post(f"/api/demandes/{nouvelle}/courrier").json()["texte"]
