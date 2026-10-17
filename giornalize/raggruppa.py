"""Raggruppamento delle notizie per argomento.

Metodo (gratuito, senza intelligenza artificiale):
1. ogni notizia diventa un elenco di parole significative (titolo + estratto);
2. ogni parola riceve un peso TF-IDF: conta di più se è rara nell'insieme
   delle notizie (es. "Crosetto") e di meno se compare ovunque (es. "governo");
3. due notizie si somigliano quanto più condividono parole pesanti
   (similarità del coseno, da 0 a 1);
4. le notizie vengono esaminate in ordine di tempo: ognuna entra nel gruppo
   a cui somiglia di più, se la somiglianza supera la soglia scelta in
   config.yaml, altrimenti apre un gruppo nuovo.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .testo import parole


@dataclass
class Gruppo:
    notizie: list[dict] = field(default_factory=list)
    centroide: dict[str, float] = field(default_factory=dict)
    parole_chiave: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        primo = min(self.notizie, key=lambda n: (n["pubblicato"], n["id"]))
        return hashlib.sha1(primo["id"].encode()).hexdigest()[:10]

    @property
    def fonti(self) -> list[str]:
        """Fonti diverse presenti nel gruppo (ogni fonte contata una volta)."""
        return list(dict.fromkeys(n["fonte"] for n in self.notizie))

    @property
    def ultimo(self) -> str:
        return max(n["pubblicato"] for n in self.notizie)


def _vettori(notizie: list[dict], peso_titolo: int) -> tuple[list[dict[str, float]], list[Counter]]:
    """Calcola i vettori TF-IDF (normalizzati) e le forme originali delle parole dei titoli."""
    conteggi: list[Counter] = []
    forme: list[Counter] = []
    for n in notizie:
        nel_titolo = parole(n["titolo"])
        c = Counter()
        for r, _ in nel_titolo:
            c[r] += peso_titolo
        for r, _ in parole(n.get("estratto", "")):
            c[r] += 1
        conteggi.append(c)
        forme.append(Counter((r, o) for r, o in nel_titolo))

    totale = len(notizie)
    frequenza_documenti = Counter()
    for c in conteggi:
        frequenza_documenti.update(c.keys())
    idf = {r: math.log((1 + totale) / (1 + df)) + 1 for r, df in frequenza_documenti.items()}

    vettori = []
    for c in conteggi:
        v = {r: (1 + math.log(tf)) * idf[r] for r, tf in c.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vettori.append({r: x / norma for r, x in v.items()})
    return vettori, forme


def similarita(a: dict, b: dict, peso_titolo: int = 2) -> float:
    """Somiglianza tra due notizie (utile per le prove e per tarare la soglia)."""
    (va, vb), _ = _vettori([a, b], peso_titolo)
    return _prodotto(va, vb)


def _norma(v: dict[str, float]) -> float:
    return math.sqrt(sum(x * x for x in v.values()))


def _prodotto(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(r, 0.0) for r, x in a.items())


def raggruppa(notizie: list[dict], soglia: float, peso_titolo: int = 2, n_parole_chiave: int = 4) -> list[Gruppo]:
    if not notizie:
        return []
    ordinate = sorted(notizie, key=lambda n: (n["pubblicato"], n["id"]))
    vettori, forme = _vettori(ordinate, peso_titolo)

    gruppi: list[Gruppo] = []
    membri: list[list[int]] = []
    norme: list[float] = []
    indice: dict[str, set[int]] = defaultdict(set)  # parola -> gruppi che la contengono

    for i, v in enumerate(vettori):
        candidati = set()
        for r in v:
            candidati |= indice[r]
        migliore, punteggio = None, 0.0
        for g in candidati:
            # v ha già norma 1: basta dividere per la norma del centroide
            s = _prodotto(v, gruppi[g].centroide) / norme[g]
            if s > punteggio:
                migliore, punteggio = g, s
        if migliore is not None and punteggio >= soglia:
            g = migliore
        else:
            gruppi.append(Gruppo())
            membri.append([])
            norme.append(1.0)
            g = len(gruppi) - 1
        gruppi[g].notizie.append(ordinate[i])
        membri[g].append(i)
        for r, x in v.items():
            gruppi[g].centroide[r] = gruppi[g].centroide.get(r, 0.0) + x
            indice[r].add(g)
        norme[g] = _norma(gruppi[g].centroide) or 1.0

    # Secondo passaggio: unisce gruppi nati separati ma molto simili tra loro
    # (succede quando la prima notizia di un argomento era poco descrittiva).
    gruppi, membri = _unisci_simili(gruppi, membri, soglia)

    for gruppo, idx in zip(gruppi, membri):
        gruppo.parole_chiave = _parole_chiave(gruppo, [forme[i] for i in idx], n_parole_chiave)
        gruppo.notizie.sort(key=lambda n: n["pubblicato"], reverse=True)
    return gruppi


def _parole_principali(centroide: dict[str, float], quante: int = 5) -> list[str]:
    return sorted(centroide, key=lambda r: -centroide[r])[:quante]


def _unisci_simili(gruppi: list[Gruppo], membri: list[list[int]], soglia: float):
    ordine = sorted(range(len(gruppi)), key=lambda g: -len(membri[g]))
    attivi: list[int] = []
    norme: dict[int, float] = {}
    indice: dict[str, list[int]] = defaultdict(list)  # parola principale -> gruppi attivi
    for g in ordine:
        centroide = gruppi[g].centroide
        norma = _norma(centroide) or 1.0
        candidati = dict.fromkeys(a for r in _parole_principali(centroide) for a in indice[r])
        destinazione = next(
            (a for a in candidati
             if _prodotto(centroide, gruppi[a].centroide) / (norma * norme[a]) >= soglia),
            None,
        )
        if destinazione is None:
            attivi.append(g)
            norme[g] = norma
            for r in _parole_principali(centroide):
                indice[r].append(g)
            continue
        gruppi[destinazione].notizie += gruppi[g].notizie
        membri[destinazione] += membri[g]
        for r, x in centroide.items():
            gruppi[destinazione].centroide[r] = gruppi[destinazione].centroide.get(r, 0.0) + x
        norme[destinazione] = _norma(gruppi[destinazione].centroide) or 1.0
    return [gruppi[a] for a in attivi], [membri[a] for a in attivi]


def _parole_chiave(gruppo: Gruppo, forme: list[Counter], quante: int) -> list[str]:
    """Le parole più rappresentative del gruppo, prese dai titoli, con la
    forma originale più usata (es. "Meloni", "manovra")."""
    peso_titoli = Counter()
    originali: dict[str, Counter] = defaultdict(Counter)
    for f in forme:
        for (r, originale), volte in f.items():
            peso_titoli[r] += 1  # in quanti titoli compare
            originali[r][originale] += volte
    classifica = sorted(
        peso_titoli,
        key=lambda r: (-(peso_titoli[r] * gruppo.centroide.get(r, 0.0)), r),
    )
    risultato = []
    for r in classifica[:quante]:
        varianti = originali[r]
        # Se la parola compare anche in minuscolo è un nome comune: la
        # scriviamo in minuscolo; altrimenti (nomi propri) con la maiuscola.
        minuscole = [o for o in varianti if o == o.lower()]
        scelta = max(minuscole or varianti, key=lambda o: (varianti[o], o))
        if scelta.isupper() and len(scelta) > 4:  # TITOLI TUTTI MAIUSCOLI
            scelta = scelta.capitalize()
        risultato.append(scelta)
    return risultato
