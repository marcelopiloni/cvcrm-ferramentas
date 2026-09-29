# -*- coding: utf-8 -*-
"""Rele na API todos os leads alterados e compara com o que o plano mandava."""
import csv
import io

from cvcrm.api import request
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("limpeza_sem_nome")


def main():
    plano = {l["idlead"]: l for l in csv.DictReader(io.open("plano_limpeza.csv", encoding="utf-8-sig"))}
    log = list(csv.DictReader(io.open("resultado_limpeza.csv", encoding="utf-8-sig")))

    ok, div, err = [], [], []
    for n, x in enumerate(log, 1):
        i = x["idlead"]
        p = plano.get(i, {})
        st, b = request("GET", "/v1/comercial/leads", params={"idlead": i})
        leads = (b or {}).get("leads") or []
        if st != 200 or not leads:
            err.append((i, f"HTTP {st}"))
            continue
        L = leads[0]
        nome_atual = (L.get("nome") or "").strip()
        sit_atual = (L.get("situacao") or {}).get("nome", "")

        problemas = []
        if p.get("acao") == "descartar" and sit_atual != "DESCARTADO":
            problemas.append(f"situacao={sit_atual!r} (esperado DESCARTADO)")
        if p.get("nome_novo", "").strip() and nome_atual != p["nome_novo"].strip():
            problemas.append(f"nome={nome_atual!r} (esperado {p['nome_novo']!r})")
        (div if problemas else ok).append((i, sit_atual, nome_atual, "; ".join(problemas)))
        if n % 50 == 0:
            print(f"  {n}/{len(log)}", flush=True)

    print(f"\nCONFERIDOS: {len(log)}")
    print(f"  corretos    : {len(ok)}")
    print(f"  divergentes : {len(div)}")
    print(f"  erro leitura: {len(err)}")
    for i, s, nm, pr in div[:20]:
        print(f"    #{i}: {pr}")
    for i, e in err[:10]:
        print(f"    #{i}: {e}")

    with io.open("conferencia_limpeza.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["idlead", "situacao_no_crm", "nome_no_crm", "problema"])
        for r in ok:
            w.writerow(list(r[:3]) + ["OK"])
        for r in div:
            w.writerow(r)
        for i, e in err:
            w.writerow([i, "", "", e])
    print("\n-> conferencia_limpeza.csv")


if __name__ == "__main__":
    main()
