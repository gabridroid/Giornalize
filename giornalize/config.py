"""Lettura e controllo di config.yaml e sources.yaml.

Gli errori sono scritti in italiano e indicano la fonte sbagliata, perché
questi due file vengono modificati a mano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parent.parent


class ErroreConfigurazione(Exception):
    pass


@dataclass
class Fonte:
    id: str
    nome: str
    categoria: str
    tipo: str = ""
    orientamento: str = ""
    orientamento_breve: str = ""
    sito: str = ""
    instagram: str = ""
    instagram_da_verificare: bool = False
    feed: list[str] = field(default_factory=list)
    sitemap: list[str] = field(default_factory=list)
    escludi: list[str] = field(default_factory=list)
    mostra_estratto: bool = True
    instagram_api: bool = False
    attiva: bool = True

    def esclusa(self, link: str) -> bool:
        """True se il link contiene uno dei pezzi elencati in "escludi"."""
        return any(pezzo in link for pezzo in self.escludi)

    @property
    def badge(self) -> str:
        return self.orientamento_breve or self.orientamento

    @property
    def instagram_url(self) -> str:
        nome = self.instagram.strip().lstrip("@")
        return f"https://www.instagram.com/{nome}/" if nome else ""


@dataclass
class Categoria:
    nome: str
    singolare: str
    plurale: str
    colore: str = "#777777"


@dataclass
class Configurazione:
    impostazioni: dict
    fonti: list[Fonte]
    categorie: list[Categoria]

    def __post_init__(self):
        self.fonti_per_id = {f.id: f for f in self.fonti}
        self.categorie_per_nome = {c.nome: c for c in self.categorie}

    def __getitem__(self, chiave):
        return self.impostazioni[chiave]


def _leggi_yaml(percorso: Path) -> dict:
    try:
        with open(percorso, encoding="utf-8") as f:
            dati = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise ErroreConfigurazione(f"Non trovo il file {percorso}")
    except yaml.YAMLError as e:
        raise ErroreConfigurazione(
            f"Il file {percorso.name} contiene un errore di scrittura "
            f"(spesso un rientro o i due punti mancanti):\n{e}"
        )
    if not isinstance(dati, dict):
        raise ErroreConfigurazione(f"Il file {percorso.name} non ha la struttura attesa")
    return dati


def carica(
    percorso_config: Path | None = None, percorso_fonti: Path | None = None
) -> Configurazione:
    impostazioni = _leggi_yaml(percorso_config or RADICE / "config.yaml")
    dati_fonti = _leggi_yaml(percorso_fonti or RADICE / "sources.yaml")

    categorie = [Categoria(**c) for c in impostazioni.get("categorie", [])]
    nomi_categorie = {c.nome for c in categorie}

    fonti: list[Fonte] = []
    visti: set[str] = set()
    campi_validi = set(Fonte.__dataclass_fields__)
    for i, voce in enumerate(dati_fonti.get("fonti") or [], start=1):
        if not isinstance(voce, dict):
            raise ErroreConfigurazione(f"sources.yaml: la fonte n. {i} non è scritta bene")
        nome = voce.get("nome") or voce.get("id") or f"n. {i}"
        sconosciuti = set(voce) - campi_validi
        if sconosciuti:
            raise ErroreConfigurazione(
                f"sources.yaml, fonte «{nome}»: campi sconosciuti {sorted(sconosciuti)}. "
                f"Campi ammessi: {sorted(campi_validi)}"
            )
        for obbligatorio in ("id", "nome", "categoria"):
            if not voce.get(obbligatorio):
                raise ErroreConfigurazione(
                    f"sources.yaml, fonte «{nome}»: manca il campo «{obbligatorio}»"
                )
        if not re.fullmatch(r"[a-z0-9_-]+", str(voce["id"])):
            raise ErroreConfigurazione(
                f"sources.yaml, fonte «{nome}»: l'id «{voce['id']}» deve contenere solo "
                "lettere minuscole, numeri, trattini (niente spazi o accenti)"
            )
        if voce["id"] in visti:
            raise ErroreConfigurazione(f"sources.yaml: l'id «{voce['id']}» è usato due volte")
        if voce["categoria"] not in nomi_categorie:
            raise ErroreConfigurazione(
                f"sources.yaml, fonte «{nome}»: la categoria «{voce['categoria']}» non esiste. "
                f"Categorie possibili: {sorted(nomi_categorie)}"
            )
        voce = dict(voce)
        for elenco in ("feed", "sitemap", "escludi"):
            valore = voce.get(elenco) or []
            if isinstance(valore, str):
                valore = [valore]
            voce[elenco] = [str(u).strip() for u in valore if u]
        for testo in ("sito", "instagram", "tipo", "orientamento", "orientamento_breve"):
            voce[testo] = str(voce.get(testo) or "").strip()
        visti.add(voce["id"])
        fonti.append(Fonte(**voce))

    for chiave in ("categorie_grandi", "categorie_alternative"):
        for nome_cat in impostazioni.get("poco_coperte", {}).get(chiave, []):
            if nome_cat not in nomi_categorie:
                raise ErroreConfigurazione(
                    f"config.yaml, poco_coperte.{chiave}: la categoria «{nome_cat}» non esiste"
                )

    return Configurazione(impostazioni=impostazioni, fonti=fonti, categorie=categorie)
