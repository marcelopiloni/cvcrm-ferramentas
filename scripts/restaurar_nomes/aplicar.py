# -*- coding: utf-8 -*-
"""Grava os nomes de volta no CV CRM lendo plano_correcao.csv.

  python aplicar.py            -> SIMULACAO (nao envia nada)
  python aplicar.py --executar -> envia de verdade
  python aplicar.py --executar --limite 5  -> envia so os 5 primeiros (teste)
"""
import csv
import sys
import time

from cvcrm.api import montar_corpo_nome, request
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("restaurar_nomes")

SEM_NOME = {"", "sem nome", "-", "--"}


def main():
    executar = "--executar" in sys.argv
    limite = None
    if "--limite" in sys.argv:
        limite = int(sys.argv[sys.argv.index("--limite") + 1])

    with open("plano_correcao.csv", encoding="utf-8-sig") as f:
        linhas = [l for l in csv.DictReader(f)
                  if l["aplicar"].strip().upper() == "S"
                  and l["nome_novo"].strip()
                  and l["nome_novo"].strip().lower() not in SEM_NOME]

    if limite:
        linhas = linhas[:limite]

    print(f"{'ENVIANDO' if executar else 'SIMULACAO'}: {len(linhas)} leads\n")
    log = []
    for n, l in enumerate(linhas, 1):
        corpo = montar_corpo_nome(l["idlead"], l["nome_novo"].strip(), l.get("idsituacao"),
                                  email=l.get("email"), telefone=l.get("telefone"))

        if not executar:
            print(f"[{n}] #{l['idlead']}: '{l['nome_atual']}' -> '{corpo['nome']}'  {corpo}")
            continue

        status, resp = request("POST", "/v1/comercial/leads", corpo=corpo,
                               extra_headers={"origemcv": "true"})
        ok = status in (200, 201) and (resp or {}).get("sucesso") not in (False, "false")
        print(f"[{n}/{len(linhas)}] #{l['idlead']} -> '{corpo['nome']}' : "
              f"{'OK' if ok else 'FALHOU'} ({status}) {str(resp)[:200]}", flush=True)
        log.append({"idlead": l["idlead"], "nome_novo": corpo["nome"], "status": status,
                    "ok": ok, "resposta": str(resp)[:500]})
        time.sleep(0.5)

    if executar and log:
        with open("resultado_aplicacao.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["idlead", "nome_novo", "status", "ok", "resposta"])
            w.writeheader()
            w.writerows(log)
        print(f"\n{sum(1 for x in log if x['ok'])}/{len(log)} aplicados. Log: resultado_aplicacao.csv")


if __name__ == "__main__":
    main()
