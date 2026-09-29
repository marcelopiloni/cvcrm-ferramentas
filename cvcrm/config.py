# -*- coding: utf-8 -*-
"""Configuracao e pasta de dados.

Tudo que e especifico da empresa (dominio, credenciais, IDs, regras) fica em
config.json na raiz do repositorio, que NAO e versionado.
"""
import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config.json"
DADOS = RAIZ / "dados"

_cache = None


def carregar():
    global _cache
    if _cache is None:
        if not CONFIG.exists():
            raise SystemExit(f"Falta {CONFIG}. Copie config.exemplo.json para config.json e preencha.")
        _cache = json.loads(CONFIG.read_text(encoding="utf-8"))
        for k in ("dominio", "email", "token"):
            if not _cache.get(k):
                raise SystemExit(f"config.json sem o campo obrigatorio '{k}'")
    return _cache


def secao(nome):
    """Uma secao do config.json (ex.: 'limpeza', 'importacao')."""
    s = carregar().get(nome)
    if not s:
        raise SystemExit(f"config.json sem a secao '{nome}'. Veja config.exemplo.json.")
    return s


def usar_pasta_dados(caso):
    """Entra em dados/<caso>/ para que os CSVs de trabalho fiquem fora do codigo."""
    p = DADOS / caso
    p.mkdir(parents=True, exist_ok=True)
    os.chdir(p)
    return p
