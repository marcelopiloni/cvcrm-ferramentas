# -*- coding: utf-8 -*-
"""Varre o CVDW /leads em paralelo e lista os leads sem nome.

O CVDW leva ~9s por pagina e sao ~591 paginas, entao sequencial daria ~90min.
Com 6 conexoes cai para ~15min. Grava incremental e retoma de onde parou:
se cair, basta rodar de novo.
"""
import csv
import io
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("limpeza_sem_nome")

os.environ.setdefault("CV_PAUSA", "0")  # a concorrencia ja limita o ritmo
from cvcrm.api import _cfg, request  # noqa: E402

VAZIOS = {"", "sem nome", "-", "--", "vazio", "none", "null"}
CAMPOS = ["idlead", "nome", "idsituacao", "situacao", "data_cad", "email", "telefone",
          "data_ultima_interacao", "ultima_data_conversao", "origem", "midia_ultimo",
          "idgestor", "gestor", "idcorretor", "corretor", "idimobiliaria", "imobiliaria",
          "empreendimento_ultimo", "referencia_data"]
ESTADO = "sem_nome.estado"
SAIDA = "sem_nome.csv"
WORKERS = 6

trava = threading.Lock()


def buscar_pagina(pagina):
    st, b = request("GET", "/leads", cvdw=True, tentativas=6,
                    params={"pagina": pagina, "registros_por_pagina": 500})
    if st != 200 or not isinstance(b, dict):
        return pagina, None, f"HTTP {st} {str(b)[:150]}"
    achados = [{c: r.get(c, "") for c in CAMPOS}
               for r in (b.get("dados") or [])
               if str(r.get("nome") or "").strip().lower() in VAZIOS]
    return pagina, achados, int(b.get("total_de_paginas") or 1)


def main():
    _cfg()  # carrega credencial antes das threads

    feitas = set()
    if os.path.exists(ESTADO):
        feitas = set(json.load(io.open(ESTADO, encoding="utf-8")))
        print(f"retomando: {len(feitas)} paginas ja processadas")

    print("descobrindo total de paginas...", flush=True)
    _, primeira, total = buscar_pagina(1)
    if primeira is None:
        raise SystemExit(f"falhou na pagina 1: {total}")
    print(f"{total} paginas de 500 leads\n", flush=True)

    modo = "a" if feitas and os.path.exists(SAIDA) else "w"
    f = io.open(SAIDA, modo, newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=CAMPOS)
    if modo == "w":
        w.writeheader()
        for r in primeira:
            w.writerow(r)
        feitas.add(1)
        f.flush()

    pendentes = [p for p in range(1, total + 1) if p not in feitas]
    achados = sum(1 for _ in io.open(SAIDA, encoding="utf-8-sig")) - 1
    falhas = []

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(buscar_pagina, p): p for p in pendentes}
            for n, fut in enumerate(as_completed(futs), 1):
                pagina, linhas, extra = fut.result()
                with trava:
                    if linhas is None:
                        falhas.append(pagina)
                    else:
                        for r in linhas:
                            w.writerow(r)
                        achados += len(linhas)
                        feitas.add(pagina)
                        f.flush()
                        json.dump(sorted(feitas), io.open(ESTADO, "w", encoding="utf-8"))
                    if n % 25 == 0 or n == len(pendentes):
                        print(f"  {n}/{len(pendentes)} paginas | sem nome: {achados} "
                              f"| falhas: {len(falhas)}", flush=True)
    finally:
        f.close()

    if falhas:
        print(f"\n{len(falhas)} paginas falharam: {falhas[:20]}")
        print("Rode o script de novo para tentar so essas.")
    else:
        if os.path.exists(ESTADO):
            os.remove(ESTADO)
        print(f"\nCONCLUIDO -> {SAIDA} | {achados} leads sem nome")


if __name__ == "__main__":
    main()
