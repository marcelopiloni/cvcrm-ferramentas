# -*- coding: utf-8 -*-
"""Procura cada linha da planilha no CV, com verificacao ESTRITA.

  python -m scripts.importar_leads.checar_duplicados <planilha.xlsx>
  (colunas: full_name, phone_number, email - padrao do export de leads do Meta)

A busca por telefone do CV e parcial ("contem"): um telefone curto ou lixo casa
com dezenas de leads alheios. Por isso cada resultado so e aceito se:
  - o e-mail for identico, ou
  - o telefone bater DDD + ultimos 8 digitos (tolera o 9o digito e o +55)
"""
import csv
import io
import re
import sys

import pandas as pd

from cvcrm.api import request
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("importar_leads")

ARQ = next((a for a in sys.argv[1:] if a.lower().endswith((".xlsx", ".xls", ".csv"))),
           "leads_para_importar.xlsx")


def normalizar_tel(t):
    """-> '+55DDNNNNNNNNN' ou '' se invalido."""
    d = re.sub(r"\D", "", t or "")
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    return f"+55{d}" if len(d) in (10, 11) else ""


def chave_tel(t):
    """DDD + ultimos 8 digitos: '+5542999744893' -> '4299744893'."""
    d = re.sub(r"\D", "", t or "")
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    return d[:2] + d[-8:] if len(d) in (10, 11) else ""


def buscar(campo, valor):
    st, b = request("GET", "/v1/comercial/leads", params={campo: valor})
    return ((b or {}).get("leads") or []) if st == 200 else []


def main():
    df = pd.read_excel(ARQ, dtype=str).fillna("")
    linhas = []
    for n, r in df.iterrows():
        email = r["email"].strip().lower()
        tel = normalizar_tel(r["phone_number"])
        ktel = chave_tel(tel)

        candidatos = {}
        if email:
            for L in buscar("email", email):
                candidatos[str(L["idlead"])] = L
        if tel:
            for L in buscar("telefone", tel):
                candidatos[str(L["idlead"])] = L

        confirmados = []
        for i, L in candidatos.items():
            por = []
            if email and (L.get("email") or "").strip().lower() == email:
                por.append("email")
            if ktel and chave_tel(L.get("telefone")) == ktel:
                por.append("telefone")
            if por:
                confirmados.append((i, "+".join(por), L))

        linhas.append({
            "linha": n + 2,
            "full_name": r["full_name"],
            "email": r["email"].strip(),
            "phone_original": r["phone_number"],
            "phone_normalizado": tel,
            "descartados_pela_verificacao": len(candidatos) - len(confirmados),
            "qtd_confirmados": len(confirmados),
            "confirmados": " | ".join(
                f"#{i} por {por} [{(L.get('situacao') or {}).get('nome','')}] "
                f"{L.get('nome','')!r} cad {str(L.get('data_cad',''))[:10]}"
                for i, por, L in confirmados),
            "ids": ";".join(i for i, _, _ in confirmados),
            "situacoes": ";".join(str((L.get("situacao") or {}).get("id", "")) for _, _, L in confirmados),
        })
        if (n + 1) % 25 == 0:
            print(f"  {n+1}/{len(df)}", flush=True)

    with io.open("duplicados.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    print("-> duplicados.csv")


if __name__ == "__main__":
    main()
