# -*- coding: utf-8 -*-
"""Descobre qual URL do painel devolve a aba Historico do lead.

  python descobrir_historico.py <idlead> "<nome antigo>"

Testa uma bateria de caminhos e marca o que contiver o nome antigo.
"""
import os
import re
import sys
import unicodedata

from cvcrm.painel import get, sessao_caiu
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("restaurar_nomes")

CANDIDATOS = [
    "/gestor/comercial/leads/{id}/administrar",
    "/gestor/comercial/leads/{id}/historico",
    "/gestor/comercial/leads/{id}/historicos",
    "/gestor/comercial/leads/{id}/log",
    "/gestor/comercial/leads/{id}/logs",
    "/gestor/comercial/leads/{id}/administrar/historico",
    "/gestor/comercial/leads/historico/{id}",
    "/gestor/comercial/leads/{id}/timeline",
    "/gestor/comercial/leads/{id}/atividades",
    "/gestor/comercial/leads/{id}/historico-alteracoes",
    "/gestor/comercial/leads/{id}/aba/historico",
    "/gestor/comercial/leads/{id}/administrar?aba=historico",
    "/gestor/comercial/leads/{id}/administrar?tab=historico",
    "/gestor/relatorios/leads/historico/html?q[1|l.idlead]={id}",
]

# marcas do texto que aparece na aba Historico
RX_HIST = re.compile(r"modificou o campo|alterou o campo|de:\s*.{1,60}\s*para:", re.I)


def norm(s):
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    idlead = sys.argv[1]
    alvo = sys.argv[2] if len(sys.argv) > 2 else None

    os.makedirs("html", exist_ok=True)
    vencedores = []
    print(f"testando {len(CANDIDATOS)} caminhos no lead #{idlead}\n")

    for i, molde in enumerate(CANDIDATOS, 1):
        caminho = molde.replace("{id}", idlead)
        status, texto = get(caminho)

        if sessao_caiu(texto):
            raise SystemExit(
                "\n>> A sessao nao esta valida (o painel devolveu a tela de login).\n"
                "   Gere de novo o curl.txt com o Copy as cURL de um request logado."
            )

        marcas = []
        if RX_HIST.search(texto):
            marcas.append("TEM TEXTO DE HISTORICO")
        if alvo and norm(alvo) in norm(texto):
            marcas.append("TEM O NOME ANTIGO")
        if marcas:
            vencedores.append((caminho, marcas))

        arq = os.path.join("html", f"{i:02d}_" + re.sub(r"[^\w]+", "_", molde)[:60] + ".html")
        with open(arq, "w", encoding="utf-8") as f:
            f.write(texto)

        sel = ("   <<<<< " + " + ".join(marcas)) if marcas else ""
        print(f"  [{status}] {len(texto):>7}b  {caminho}{sel}")

    print()
    if vencedores:
        print(">> ACHOU:")
        for c, m in vencedores:
            print(f"   {c}  ({', '.join(m)})")
        print("\n   Me manda essa saida que eu escrevo o extrator em cima do HTML salvo em html/")
    else:
        print(">> Nenhum caminho devolveu o historico.")
        print("   Plano B: abra a aba Historico do lead no navegador com o F12 na")
        print("   guia Network, veja qual request carrega a lista e me manda o")
        print("   'Copy as cURL' DESSE request especifico.")


if __name__ == "__main__":
    main()
