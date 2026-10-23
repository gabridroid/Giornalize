"""Temi da seguire (file temi.yaml): argomenti scelti a mano, descritti
con le parole da cercare nei titoli e negli estratti.

Regola di scrittura, la stessa spiegata in cima a temi.yaml:
- la virgola vuol dire "oppure": basta una delle parole;
- il + vuol dire "e anche": serve almeno una parola di ogni gruppo;
- singolare e plurale, maschile e femminile vanno bene da soli
  ("multa" trova anche "multe", "denunciato" anche "denunciati");
- l'asterisco trova tutte le parole che iniziano così ("denunc*").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import RADICE, ErroreConfigurazione
from .testo import radice as _radice_base

FILE_TEMI = RADICE / "temi.yaml"


@dataclass
class Parola:
    """Una parola (o un'espressione di più parole) da cercare."""
    testo: str
    pezzi: list[str]  # radici delle parole; l'ultima senza radice se con *
    prefisso: bool = False


@dataclass
class Tema:
    id: str
    nome: str
    cerca: str
    gruppi: list[list[Parola]] = field(default_factory=list)

    def corrisponde(self, testo: str) -> bool:
        parole = _parole(testo)
        radici = [radice(p) for p in parole]
        return all(any(_trova(p, parole, radici) for p in gruppo) for gruppo in self.gruppi)

    @property
    def descrizione_gruppi(self) -> list[str]:
        return [", ".join(p.testo for p in gruppo) for gruppo in self.gruppi]


def radice(parola: str) -> str:
    """Come per il raggruppamento, ma toglie anche la "i" di "foglio/fogli",
    "camicia/camicie": così singolare e plurale coincidono."""
    r = _radice_base(parola)
    if r != parola and len(r) > 4 and r.endswith("i"):
        r = r[:-1]
    return r


def _semplifica(testo: str) -> str:
    t = unicodedata.normalize("NFKD", testo.lower().replace("’", "'"))
    return "".join(c for c in t if not unicodedata.combining(c))


def _parole(testo: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _semplifica(testo))


def _trova(parola: Parola, parole: list[str], radici: list[str]) -> bool:
    n = len(parola.pezzi)
    for i in range(len(parole) - n + 1):
        uguali = all(radici[i + k] == parola.pezzi[k] for k in range(n - 1))
        ultima = (parole[i + n - 1].startswith(parola.pezzi[-1]) if parola.prefisso
                  else radici[i + n - 1] == parola.pezzi[-1])
        if uguali and ultima:
            return True
    return False


def _parola(testo: str) -> Parola:
    prefisso = testo.endswith("*")
    pezzi = _parole(testo.rstrip("*"))
    if not pezzi:
        raise ValueError(testo)
    radici = [radice(p) for p in pezzi]
    if prefisso:
        radici[-1] = pezzi[-1]
    return Parola(testo=testo, pezzi=radici, prefisso=prefisso)


def interpreta(cerca: str) -> list[list[Parola]]:
    """'denunciati, multe + tir, agricoltori' -> [[denunciati, multe], [tir, agricoltori]]"""
    gruppi = []
    for pezzo in cerca.split("+"):
        parole = [p.strip() for p in pezzo.split(",") if p.strip()]
        if parole:
            gruppi.append([_parola(p) for p in parole])
    return gruppi


def carica_temi(percorso: Path | None = None) -> list[Tema]:
    percorso = percorso or FILE_TEMI
    if not percorso.exists():
        return []
    try:
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ErroreConfigurazione(
            f"Il file {percorso.name} contiene un errore di scrittura "
            f"(spesso un rientro o i due punti mancanti):\n{e}"
        )
    temi: list[Tema] = []
    visti: set[str] = set()
    for i, voce in enumerate(dati.get("temi") or [], start=1):
        if not isinstance(voce, dict) or not voce.get("nome") or not voce.get("cerca"):
            raise ErroreConfigurazione(f"{percorso.name}: il tema n. {i} deve avere «nome» e «cerca»")
        if voce.get("attivo") is False:
            continue
        nome, cerca = str(voce["nome"]).strip(), str(voce["cerca"]).strip()
        try:
            gruppi = interpreta(cerca)
        except ValueError as e:
            raise ErroreConfigurazione(f"{percorso.name}, tema «{nome}»: la parola «{e}» non è valida")
        if not gruppi:
            raise ErroreConfigurazione(f"{percorso.name}, tema «{nome}»: «cerca» è vuoto")
        id_tema = re.sub(r"[^a-z0-9]+", "-", _semplifica(nome)).strip("-") or f"tema-{i}"
        while id_tema in visti:
            id_tema += "-2"
        visti.add(id_tema)
        temi.append(Tema(id=id_tema, nome=nome, cerca=cerca, gruppi=gruppi))
    return temi
