"""Stockage (CR.2) et assemblage de la demande complète (spec §3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kaldera.interface.construction import ErreurSaisie, construire_demande
from kaldera.interface.stockage import Stockage

ASSURE = {
    "assure": {"id_client": "CL-1", "nom": "Martin", "code_postal": "69003"},
    "historique": {
        "sinistres_12_mois": 1
    },  # ancien format de stockage : l'historique vient maintenant de la saisie
}
CONTRAT = {"numero": "CTR-1", "formule": "confort"}


@pytest.fixture
def stockage(tmp_path: Path) -> Stockage:
    s = Stockage(tmp_path)
    s.enregistrer_assure("CL-1", ASSURE)
    s.enregistrer_contrat("CTR-1", CONTRAT, id_client="CL-1")
    return s


def saisie(**plus: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "numero_contrat": "CTR-1",
        "sinistres_12_mois": 2,
        "sinistre": {
            "type": "vol",
            "date_survenance": "2026-08-14",
            "date_declaration": "2026-08-15",
            "montant_declare": 900.0,
            "description": "Cambriolage",
        },
        "pieces": [{"type": "facture", "lisible": True, "montant": 900.0}],
    }
    base.update(plus)
    return base


def test_la_demande_reprend_le_stockage_et_la_saisie(stockage: Stockage) -> None:
    d = construire_demande(saisie(), stockage, "KAL-26-0101")
    assert d["reference"] == "KAL-26-0101"
    assert d["assure"] == ASSURE["assure"] and d["contrat"] == CONTRAT
    assert d["historique"] == {"sinistres_12_mois": 2}
    assert d["sinistre"]["type"] == "vol"
    assert d["espace_assure"] == {"depots": []}
    assert d["pieces"] == saisie()["pieces"]


def test_contrat_introuvable_refuse_a_la_saisie(stockage: Stockage) -> None:
    with pytest.raises(ErreurSaisie, match="contrat 'X' introuvable"):
        construire_demande(saisie(numero_contrat="X"), stockage, "KAL-26-0101")


def test_contrat_sans_assure_rattache_refuse(stockage: Stockage) -> None:
    stockage.enregistrer_contrat("CTR-2", CONTRAT)
    with pytest.raises(ErreurSaisie, match="aucun assuré rattaché"):
        construire_demande(saisie(numero_contrat="CTR-2"), stockage, "KAL-26-0101")


def test_assure_rattache_disparu_refuse(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    s.enregistrer_contrat("CTR-3", CONTRAT, id_client="CL-404")
    with pytest.raises(ErreurSaisie, match="assuré 'CL-404' introuvable"):
        construire_demande(saisie(numero_contrat="CTR-3"), s, "KAL-26-0101")


def test_sinistres_12_mois_absent_vaut_zero(stockage: Stockage) -> None:
    s = saisie()
    del s["sinistres_12_mois"]
    assert construire_demande(s, stockage, "KAL-26-0101")["historique"] == {"sinistres_12_mois": 0}


def test_saisie_invalide_refusee_avant_le_moteur(stockage: Stockage) -> None:
    with pytest.raises(ErreurSaisie) as e:
        construire_demande(saisie(numero_contrat=""), stockage, "KAL-26-0101")
    assert e.value.erreurs


def test_le_stockage_n_est_pas_modifie_par_la_construction(stockage: Stockage) -> None:
    d = construire_demande(saisie(), stockage, "KAL-26-0101")
    d["contrat"]["formule"] = "premium"
    assert stockage.contrat("CTR-1")["formule"] == "confort"


def test_stockage_persistant(tmp_path: Path) -> None:
    Stockage(tmp_path).enregistrer_assure("CL-1", ASSURE)
    assert Stockage(tmp_path).assure("CL-1") == ASSURE
    assert Stockage(tmp_path).assures() == ["CL-1"]


def test_sauvegarde_et_relecture_d_une_demande(stockage: Stockage) -> None:
    d = construire_demande(saisie(), stockage, "KAL-26-0101")
    stockage.sauvegarder_demande(d)
    assert stockage.demande("KAL-26-0101") == d
    assert stockage.demandes() == ["KAL-26-0101"]


def test_amorcage_depuis_les_scenarios(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    nb = s.amorcer(Path("eval/scenarios.jsonl"))
    assert nb > 10 and "CL-10021" in s.assures() and "CTR-778801" in s.contrats()


# --- Contrat enregistré depuis un fichier (CR.6) : traçabilité dans le stockage seulement ------


def test_contrat_enregistre_avec_son_fichier_et_l_origine_de_chaque_champ(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    contrat = {
        "numero": "CTR-9",
        "formule": "confort",
        "date_souscription": "2025-03-12",
        "statut": "actif",
        "cotisations_a_jour": True,
    }
    origines = {"numero": "modele", "formule": "humain", "date_souscription": "modele"}
    s.enregistrer_contrat(
        "CTR-9", contrat, source={"nom": "c.pdf", "contenu": b"%PDF", "origines": origines}
    )
    assert s.contrat("CTR-9") == contrat  # la demande ne reçoit que les 5 champs de la spec §3
    meta = s.tracabilite("CTR-9")
    assert meta is not None and meta["origines"] == origines and meta["fichier"].endswith(".pdf")
    assert (tmp_path / "contrats_pdf" / meta["fichier"]).read_bytes() == b"%PDF"


def test_la_demande_ne_porte_que_les_cinq_champs_du_contrat(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    s.enregistrer_assure("CL-1", ASSURE)
    contrat = {
        "numero": "CTR-9",
        "formule": "confort",
        "date_souscription": "2025-03-12",
        "statut": "actif",
        "cotisations_a_jour": True,
    }
    s.enregistrer_contrat(
        "CTR-9", contrat, source={"nom": "c.png", "contenu": b"x", "origines": {}}, id_client="CL-1"
    )
    d = construire_demande(saisie(numero_contrat="CTR-9"), s, "KAL-26-0101")
    assert set(d["contrat"]) == set(contrat)


def test_contrat_sans_fichier_n_a_ni_fichier_ni_origines(stockage: Stockage) -> None:
    assert stockage.tracabilite("CTR-1") == {"id_client": "CL-1"}


def test_nom_de_fichier_dangereux_ne_sort_pas_du_dossier(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    s.enregistrer_contrat(
        "CTR-9",
        {"numero": "CTR-9"},
        source={"nom": "../../evil.pdf", "contenu": b"x", "origines": {}},
    )
    fichiers = list((tmp_path / "contrats_pdf").iterdir())
    assert len(fichiers) == 1 and fichiers[0].parent == tmp_path / "contrats_pdf"


# --- Référence générée par le système : KAL-AA-NNNN, numéro suivant de l'année ------------------


def test_premiere_reference_de_l_annee(tmp_path: Path) -> None:
    assert Stockage(tmp_path).prochaine_reference(26) == "KAL-26-0001"


def test_la_reference_suit_le_plus_grand_numero_de_l_annee(stockage: Stockage) -> None:
    for ref in ("KAL-26-0001", "KAL-26-0007", "KAL-25-0400"):
        stockage.sauvegarder_demande({"reference": ref})
    assert stockage.prochaine_reference(26) == "KAL-26-0008"
    assert stockage.prochaine_reference(25) == "KAL-25-0401"
    assert stockage.prochaine_reference(27) == "KAL-27-0001"


def test_reference_epuisee_apres_9999(stockage: Stockage) -> None:
    stockage.sauvegarder_demande({"reference": "KAL-26-9999"})
    with pytest.raises(RuntimeError, match="9999"):
        stockage.prochaine_reference(26)


# --- Rattachement de l'assuré au contrat, identifiant généré -----------------------------------


def test_le_contrat_garde_son_assure_rattache(stockage: Stockage) -> None:
    assert stockage.assure_du_contrat("CTR-1") == "CL-1"
    assert stockage.assure_du_contrat("inconnu") is None


def test_le_rattachement_ne_pollue_pas_le_contrat(stockage: Stockage) -> None:
    assert stockage.contrat("CTR-1") == CONTRAT


def test_rattachement_conserve_avec_le_fichier_d_origine(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    s.enregistrer_contrat(
        "CTR-9",
        CONTRAT,
        source={"nom": "c.pdf", "contenu": b"x", "origines": {"nom": "modele"}},
        id_client="CL-7",
    )
    meta = s.tracabilite("CTR-9")
    assert (
        meta is not None and meta["id_client"] == "CL-7" and meta["origines"] == {"nom": "modele"}
    )


def test_premier_identifiant_client(tmp_path: Path) -> None:
    assert Stockage(tmp_path).prochain_id_client() == "CL-10001"


def test_identifiant_client_suit_le_plus_grand(stockage: Stockage) -> None:
    stockage.enregistrer_assure("CL-13561", ASSURE)
    stockage.enregistrer_assure("CL-abc", ASSURE)
    assert stockage.prochain_id_client() == "CL-13562"


def test_amorcage_rattache_chaque_contrat_a_son_assure(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    s.amorcer(Path("eval/scenarios.jsonl"))
    assert s.assure_du_contrat("CTR-778801") == "CL-10021"


# --- Fiche et lettre conservées pour la suite de la chaîne (addendum n°3) --------------------


def test_fiche_sauvegardee_et_relue(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    s.sauvegarder_fiche({"reference": "KAL-26-0001", "issue": "decision"})
    assert s.fiche("KAL-26-0001") == {"reference": "KAL-26-0001", "issue": "decision"}
    assert s.fiche("KAL-26-0002") is None


def test_courrier_sauvegarde_et_relu(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    s.sauvegarder_courrier(
        "KAL-26-0001", {"texte": "Madame…", "origine": "standard", "envoye_le": None}
    )
    assert s.courrier("KAL-26-0001")["texte"] == "Madame…"  # type: ignore[index]
    assert s.courrier("../x") is None
