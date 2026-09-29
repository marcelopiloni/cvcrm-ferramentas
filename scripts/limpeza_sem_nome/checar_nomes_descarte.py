# -*- coding: utf-8 -*-
"""Para os leads marcados como 'descartar', descobre se existe nome recuperavel.
Escreve nomes_dos_descartes.csv. Retomavel."""
import csv
import io
import os

from cvcrm.historico import eventos_de_nome, nome_perdido
from cvcrm.painel import get, sessao_caiu
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("limpeza_sem_nome")


def main():
    SAIDA = "nomes_dos_descartes.csv"

    plano = list(csv.DictReader(io.open("plano_limpeza.csv", encoding="utf-8-sig")))
    alvo = [x for x in plano if x["acao"] == "descartar"]

    feitos = set()
    if os.path.exists(SAIDA):
        feitos = {l["idlead"] for l in csv.DictReader(io.open(SAIDA, encoding="utf-8-sig"))}
    fila = [x for x in alvo if x["idlead"] not in feitos]
    print(f"{len(alvo)} descartes | {len(feitos)} ja checados | {len(fila)} na fila\n")

    modo = "a" if feitos else "w"
    f = io.open(SAIDA, modo, newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=["idlead", "nome_recuperavel", "situacao", "dias_parado"])
    if modo == "w":
        w.writeheader()

    com, sem = 0, 0
    try:
        for n, x in enumerate(fila, 1):
            st, t = get(f"/gestor/comercial/leads/{x['idlead']}/historico")
            if sessao_caiu(t):
                print(f"\n>> SESSAO EXPIROU. {n-1} checados, salvos em {SAIDA}.")
                break
            nome, _ = nome_perdido(eventos_de_nome(t)) if st == 200 else ("", None)
            w.writerow({"idlead": x["idlead"], "nome_recuperavel": nome,
                        "situacao": x["situacao"], "dias_parado": x["dias_parado"]})
            f.flush()
            com += bool(nome)
            sem += not nome
            if n % 50 == 0 or n == len(fila):
                print(f"  {n}/{len(fila)} | com nome: {com} | sem nome: {sem}", flush=True)
    finally:
        f.close()
    print(f"\n-> {SAIDA}")


if __name__ == "__main__":
    main()
