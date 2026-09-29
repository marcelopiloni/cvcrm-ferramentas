# -*- coding: utf-8 -*-
"""Sonda todos os endpoints possiveis de um lead para descobrir ONDE o nome antigo
ainda existe. Uso:  python probe.py <idlead> "<nome antigo>"
"""
import json
import sys
import unicodedata

from cvcrm.api import request
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("restaurar_nomes")

ALVOS = [
    # (rotulo, metodo, caminho, params, cvdw)
    ("v1 lead atual",      "GET", "/v1/comercial/leads",            {"idlead": None}, False),
    ("v1 interacoes",      "GET", "/v1/comercial/leads/interacoes", {"idlead": None, "registros_por_pagina": 100}, False),
    ("v1 conversoes",      "GET", "/v1/comercial/leads-conversao",  {"idlead": None, "registros_por_pagina": 100}, False),
    ("v1 atendimentos",    "GET", "/v1/comercial/leads/atendimentos", {"idlead": None}, False),
    ("v1 tarefas",         "GET", "/v1/comercial/leads/tarefas",    {"idlead": None}, False),
    # tentativas nao documentadas de historico de campos
    ("? historico (a)",    "GET", "/v1/comercial/leads/historico",  {"idlead": None}, False),
    ("? historico (b)",    "GET", "/v1/comercial/leads/historicos", {"idlead": None}, False),
    ("? historico (c)",    "GET", "/v1/comercial/leads/{id}/historico", {}, False),
    ("? logs",             "GET", "/v1/comercial/leads/logs",       {"idlead": None}, False),
]


def norm(s):
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def main():
    if len(sys.argv) < 2:
        raise SystemExit('uso: python probe.py <idlead> ["nome esperado"]')
    idlead = sys.argv[1]
    esperado = sys.argv[2] if len(sys.argv) > 2 else None

    resultado = {}
    for rotulo, metodo, caminho, params, cvdw in ALVOS:
        p = {k: (idlead if v is None else v) for k, v in params.items()}
        c = caminho.replace("{id}", idlead)
        status, body = request(metodo, c, params=p, cvdw=cvdw, tentativas=1)
        resultado[rotulo] = {"caminho": c, "status": status, "resposta": body}
        txt = json.dumps(body, ensure_ascii=False)
        marca = ""
        if esperado and norm(esperado) in norm(txt):
            marca = "  <<<< CONTEM O NOME ESPERADO"
        elif esperado:
            # tenta so o primeiro nome
            if norm(esperado.split()[0]) in norm(txt):
                marca = "  <<<< contem o primeiro nome"
        print(f"[{status}] {rotulo:20s} {c}  ({len(txt)} bytes){marca}")

    saida = f"probe_{idlead}.json"
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"\nrespostas completas salvas em {saida}")


if __name__ == "__main__":
    main()
