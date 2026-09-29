# -*- coding: utf-8 -*-
"""Rele o historico dos leads marcados como 'revisar' para (a) confirmar se
tiveram nome antes e (b) reclassifica-los depois de mudar as situacoes permitidas
no config.json."""
import csv
import io

from cvcrm.historico import eventos_de_nome, nome_perdido, todos_eventos
from cvcrm.regras import classificar
from cvcrm.painel import get, sessao_caiu
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("limpeza_sem_nome")


def main():
    plano = list(csv.DictReader(io.open("plano_limpeza.csv", encoding="utf-8-sig")))
    alvo = [x for x in plano if x["acao"] == "revisar"]
    print(f"validando {len(alvo)} leads\n")

    por_id = {}
    for n, x in enumerate(alvo, 1):
        st, t = get(f"/gestor/comercial/leads/{x['idlead']}/historico")
        if sessao_caiu(t) or st != 200:
            print(f"  #{x['idlead']}: falhou (HTTP {st})")
            continue
        evs_nome = eventos_de_nome(t)
        nome, ev = nome_perdido(evs_nome)
        acao, motivo, ultima = classificar(x["idsituacao"], todos_eventos(t), nome)
        por_id[x["idlead"]] = (nome, acao, motivo, evs_nome)
        if n % 20 == 0 or n == len(alvo):
            print(f"  {n}/{len(alvo)}", flush=True)

    print()
    import collections
    print("=== TIVERAM NOME ANTES? ===")
    com = {i: v for i, v in por_id.items() if v[0]}
    print(f"  com nome recuperavel: {len(com)}")
    for i, (nome, acao, motivo, _) in com.items():
        print(f"     #{i} -> {nome!r}  (nova acao: {acao})")
    print(f"  sem nome recuperavel: {len(por_id)-len(com)}")
    print()
    print("=== NOVA CLASSIFICACAO ===")
    for a, n in collections.Counter(v[1] for v in por_id.values()).most_common():
        print(f"  {a:16} {n}")

    # grava de volta no plano
    mud = 0
    for x in plano:
        if x["idlead"] in por_id:
            nome, acao, motivo, _ = por_id[x["idlead"]]
            if acao != x["acao"] or nome != x["nome_novo"]:
                x["acao"], x["motivo"] = acao, motivo
                x["nome_novo"] = nome if acao == "restaurar_nome" else x["nome_novo"]
                if nome:
                    x["nome_novo"] = nome
                x["idsituacao_novo"] = 3 if acao == "descartar" else ""
                mud += 1
    with io.open("plano_limpeza.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(plano[0].keys()))
        w.writeheader()
        w.writerows(plano)
    print(f"\n{mud} linhas atualizadas em plano_limpeza.csv")


if __name__ == "__main__":
    main()
