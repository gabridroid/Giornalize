"""Diagnosi dell'API di Instagram: chiede a Meta cosa può fare il codice di
accesso salvato su GitHub e scrive il risultato in data/diagnosi_instagram.json.
Il codice di accesso non viene mai scritto nel file."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests


def _chiama(url: str, params: dict) -> dict:
    try:
        risposta = requests.get(url, params=params, timeout=20)
        dati = risposta.json()
    except Exception as e:  # rete o risposta non leggibile
        return {"errore_rete": str(e)}
    if "error" in dati:
        e = dati["error"]
        return {"errore": {k: e.get(k) for k in ("message", "type", "code", "error_subcode", "error_user_msg")}}
    return dati


def esegui(percorso: Path, versione: str = "v24.0", nomi_da_verificare: list[str] | None = None) -> dict:
    token = os.environ.get("INSTAGRAM_TOKEN", "")
    account = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
    base = f"https://graph.facebook.com/{versione}"
    risultato: dict = {
        "quando": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "token_presente": bool(token),
        "account_id_presente": bool(account),
    }
    if token:
        info = _chiama(f"{base}/debug_token", {"input_token": token, "access_token": token})
        dati = info.get("data", info)
        risultato["codice"] = {k: dati.get(k) for k in (
            "type", "is_valid", "app_id", "application", "scopes", "granular_scopes",
            "expires_at", "data_access_expires_at", "profile_id", "error") if k in dati} if isinstance(dati, dict) else dati
        risultato.get("codice", {}).pop("profile_id", None)
    if token and account:
        # Solo dati pubblici dell'account Instagram di Giornalize: mai nomi di persone.
        proprio = _chiama(f"{base}/{account}", {"fields": "username,media_count", "access_token": token})
        risultato["proprio_account"] = proprio
        nome_utente = proprio.get("username")
        if nome_utente:
            risultato["business_discovery_su_se_stesso"] = _chiama(f"{base}/{account}", {
                "fields": f"business_discovery.username({nome_utente}){{username}}", "access_token": token})
        risultato["business_discovery_su_altro_account"] = _chiama(f"{base}/{account}", {
            "fields": "business_discovery.username(instagram){username,media_count}", "access_token": token})
    if token and account and nomi_da_verificare:
        # Per ogni account Instagram in sources.yaml: esiste ed è professionale?
        verifiche = {}
        for nome in nomi_da_verificare:
            r = _chiama(f"{base}/{account}", {
                "fields": f"business_discovery.username({nome}){{username,media_count}}", "access_token": token})
            verifiche[nome] = "ok" if "business_discovery" in r else r.get("errore", r).get("message", "errore")
        risultato["verifica_account"] = verifiche
    testo = json.dumps(risultato, ensure_ascii=False, indent=1)
    assert not token or token not in testo, "il codice non deve finire nel file"
    percorso.write_text(testo, encoding="utf-8")
    return risultato
