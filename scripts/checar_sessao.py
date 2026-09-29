# -*- coding: utf-8 -*-
"""Diz se o curl.txt / cookie.txt colado na raiz esta valendo.

  python -m scripts.checar_sessao <idlead de teste>
"""
import sys

from cvcrm.painel import carregar_headers, get, sessao_caiu


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    idlead = sys.argv[1]
    h = carregar_headers()
    print(f"  cookie com {len(h.get('Cookie', ''))} caracteres")

    status, texto = get(f"/gestor/comercial/leads/{idlead}/administrar")
    print(f"  HTTP {status}, {len(texto)} bytes")
    if sessao_caiu(texto) or status != 200 or idlead not in texto:
        raise SystemExit("  >> SESSAO INVALIDA: refaca o Copy as cURL com o navegador logado.")

    _, hist = get(f"/gestor/comercial/leads/{idlead}/historico")
    n = hist.count("linhadotempo-box")
    if not n:
        raise SystemExit("  >> SESSAO INVALIDA: a aba Historico nao devolveu a linha do tempo.")
    print(f"  >> SESSAO OK. A aba Historico voltou com {n} eventos.")


if __name__ == "__main__":
    main()
