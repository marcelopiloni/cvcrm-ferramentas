# -*- coding: utf-8 -*-
"""Rele o lote leads na API e compara com o que o plano mandava gravar."""
import csv
import io

from cvcrm.api import request
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("restaurar_nomes")


def main():
    plano = list(csv.DictReader(io.open("plano_correcao.csv", encoding="utf-8-sig")))
    alvo = {l["idlead"]: l["nome_novo"].strip() for l in plano if l["aplicar"] == "S"}

    ok, divergentes, erros = [], [], []
    for n, (i, esperado) in enumerate(alvo.items(), 1):
        st, b = request("GET", "/v1/comercial/leads", params={"idlead": i})
        leads = (b or {}).get("leads") or []
        if st != 200 or not leads:
            erros.append((i, f"HTTP {st}"))
            continue
        atual = (leads[0].get("nome") or "").strip()
        (ok if atual == esperado else divergentes).append((i, esperado, atual))
        if n % 25 == 0:
            print(f"  {n}/{len(alvo)}", flush=True)

    print()
    print(f"CONFERIDOS : {len(alvo)}")
    print(f"  corretos : {len(ok)}")
    print(f"  divergentes: {len(divergentes)}")
    print(f"  erros de leitura: {len(erros)}")
    for i, esp, at in divergentes[:20]:
        print(f"    #{i}: esperado {esp!r}, esta {at!r}")
    for i, e in erros[:20]:
        print(f"    #{i}: {e}")

    with io.open("conferencia.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["idlead", "esperado", "no_crm", "status"])
        for i, esp, at in ok:
            w.writerow([i, esp, at, "OK"])
        for i, esp, at in divergentes:
            w.writerow([i, esp, at, "DIVERGENTE"])
        for i, e in erros:
            w.writerow([i, alvo.get(i, ""), "", e])
    print("\n-> conferencia.csv")


if __name__ == "__main__":
    main()
