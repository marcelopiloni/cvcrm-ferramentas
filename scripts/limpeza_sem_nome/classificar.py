# -*- coding: utf-8 -*-
"""Le o historico de cada lead de sem_nome.csv e classifica.

Grava incremental em plano_limpeza.csv e retoma de onde parou.
  python classificar.py            # tudo
  python classificar.py --limite 5 # amostra
"""
import collections
import csv
import io
import os
import sys
from datetime import datetime

from cvcrm.historico import eventos_de_nome, nome_perdido, todos_eventos
from cvcrm.regras import ID_DESCARTADO, SITUACOES_PERMITIDAS, classificar
from cvcrm.painel import get, sessao_caiu
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("limpeza_sem_nome")

SAIDA = "plano_limpeza.csv"
CAMPOS = ["idlead", "acao", "motivo", "nome_novo", "idsituacao_novo",
          "nome_atual", "idsituacao", "situacao", "email", "telefone",
          "ultimo_atendimento", "dias_parado", "qtd_eventos", "qtd_eventos_nome",
          "apagado_por", "apagado_em", "obs"]


def ja_feitos():
    if not os.path.exists(SAIDA):
        return set()
    return {l["idlead"] for l in csv.DictReader(io.open(SAIDA, encoding="utf-8-sig"))}


def main():
    limite = int(sys.argv[sys.argv.index("--limite") + 1]) if "--limite" in sys.argv else None
    todos = list(csv.DictReader(io.open("sem_nome.csv", encoding="utf-8-sig")))
    # so os que estao literalmente com "Sem nome" (nas 3 grafias que a base tem).
    # Leads com nome realmente vazio ficam de fora.
    leads = [l for l in todos if (l.get("nome") or "").strip().lower() == "sem nome"]
    vazios = len(todos) - len(leads)
    if vazios:
        print(f"({vazios} leads com nome vazio ficaram de fora do escopo)")
    feitos = ja_feitos()
    fila = [l for l in leads if l["idlead"] not in feitos]
    if limite:
        fila = fila[:limite]

    print(f"{len(leads)} leads sem nome | {len(feitos)} ja processados | {len(fila)} na fila\n")
    modo = "a" if feitos else "w"
    f = io.open(SAIDA, modo, newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=CAMPOS)
    if modo == "w":
        w.writeheader()

    agora = datetime.now()
    contagem = collections.Counter()
    try:
        for n, l in enumerate(fila, 1):
            i = l["idlead"]
            st, txt = get(f"/gestor/comercial/leads/{i}/historico")
            if sessao_caiu(txt):
                print(f"\n>> SESSAO EXPIROU no lead #{i}.")
                print(f"   {n-1} processados nesta rodada, tudo salvo em {SAIDA}.")
                print("   Refaca o curl.txt e rode 'python classificar.py' de novo.")
                break
            if st != 200 or not txt:
                w.writerow({"idlead": i, "acao": "erro", "obs": f"HTTP {st}"})
                contagem["erro"] += 1
                f.flush()
                continue

            eventos = todos_eventos(txt)
            evs_nome = eventos_de_nome(txt)
            nome, ev_apagou = nome_perdido(evs_nome)
            acao, motivo, ultima = classificar(l.get("idsituacao"), eventos, nome, agora)
            w.writerow({
                "idlead": i,
                "acao": acao,
                "motivo": motivo,
                "nome_novo": nome if acao == "restaurar_nome" else "",
                "idsituacao_novo": ID_DESCARTADO if acao == "descartar" else "",
                "nome_atual": l.get("nome", ""),
                "idsituacao": l.get("idsituacao", ""),
                "situacao": l.get("situacao", ""),
                "email": l.get("email", ""),
                "telefone": l.get("telefone", ""),
                "ultimo_atendimento": ultima.strftime("%d/%m/%Y %H:%M") if ultima else "",
                "dias_parado": (agora - ultima).days if ultima else "",
                "qtd_eventos": len(eventos),
                "qtd_eventos_nome": len(evs_nome),
                "apagado_por": (ev_apagou or {}).get("quem", "")[:60],
                "apagado_em": (ev_apagou or {}).get("quando", ""),
                "obs": "",
            })
            f.flush()
            contagem[acao] += 1
            if n % 25 == 0 or n == len(fila):
                print(f"  {n}/{len(fila)}  {contagem}", flush=True)
    finally:
        f.close()

    print(f"\n-> {SAIDA}")
    for k, v in contagem.items():
        print(f"   {k:16} {v}")


if __name__ == "__main__":
    main()
