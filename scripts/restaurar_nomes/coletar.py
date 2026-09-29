# -*- coding: utf-8 -*-
"""Coleta os dados necessarios para reconstruir os nomes.

  python coletar.py atual        -> estado atual dos leads de leads_ids.csv
  python coletar.py conversoes   -> dump completo do CVDW /leads/conversoes
  python coletar.py interacoes   -> interacoes (v1) dos leads de leads_ids.csv
"""
import csv
import json
import sys

from cvcrm.api import paginar_cvdw, request
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("restaurar_nomes")


def ids():
    with open("leads_ids.csv", encoding="utf-8-sig") as f:
        return [l["idlead"] for l in csv.DictReader(f)]


def _achatar(lead):
    """Extrai os campos uteis do retorno v1 de um lead."""
    def g(*ks):
        v = lead
        for k in ks:
            v = (v or {}).get(k) if isinstance(v, dict) else None
        return v
    return {
        "idlead": lead.get("idlead"),
        "nome_atual": lead.get("nome") or "",
        "email": lead.get("email") or "",
        "telefone": lead.get("telefone") or "",
        "idsituacao": g("situacao", "id") or lead.get("idsituacao") or "",
        "situacao": g("situacao", "nome") or "",
        "origem": g("origem", "nome") or lead.get("origem") or "",
        "data_cad": lead.get("data_cad") or lead.get("cadastro") or "",
    }


def coletar_atual():
    linhas = []
    lista = ids()
    for n, i in enumerate(lista, 1):
        status, body = request("GET", "/v1/comercial/leads", params={"idlead": i})
        leads = (body or {}).get("leads") or []
        if status == 200 and leads:
            linhas.append(_achatar(leads[0]))
        else:
            linhas.append({"idlead": i, "nome_atual": f"<ERRO {status}>", "email": "",
                           "telefone": "", "idsituacao": "", "situacao": "",
                           "origem": "", "data_cad": ""})
        if n % 10 == 0 or n == len(lista):
            print(f"  {n}/{len(lista)}", flush=True)
    campos = ["idlead", "nome_atual", "email", "telefone", "idsituacao", "situacao", "origem", "data_cad"]
    with open("leads_atual.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    print(f"-> leads_atual.csv ({len(linhas)} leads)")


def coletar_conversoes():
    alvo = set(ids())
    total = achados = 0
    with open("conversoes.jsonl", "w", encoding="utf-8") as f:
        for reg in paginar_cvdw("/leads/conversoes", por_pagina=500):
            total += 1
            if str(reg.get("idlead")) in alvo:
                achados += 1
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    print(f"-> conversoes.jsonl: {achados} conversoes dos nossos leads (de {total} varridas)")


def coletar_interacoes():
    lista = ids()
    with open("interacoes.jsonl", "w", encoding="utf-8") as f:
        for n, i in enumerate(lista, 1):
            status, body = request("GET", "/v1/comercial/leads/interacoes",
                                   params={"idlead": i, "registros_por_pagina": 200})
            for d in ((body or {}).get("dados") or []):
                d["_idlead"] = i
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
            if n % 10 == 0 or n == len(lista):
                print(f"  {n}/{len(lista)}", flush=True)
    print("-> interacoes.jsonl")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"atual": coletar_atual, "conversoes": coletar_conversoes,
     "interacoes": coletar_interacoes}.get(cmd, lambda: sys.exit(__doc__))()
