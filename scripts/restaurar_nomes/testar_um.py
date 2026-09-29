# -*- coding: utf-8 -*-
"""Teste ponta a ponta em UM lead antes de mexer no lote.

  python testar_um.py <idlead>
      -> so LE: valida credenciais, mostra o lead hoje e procura o nome antigo

  python testar_um.py <idlead> --nome "<nome antigo>" --aplicar
      -> ESCREVE esse nome no lead e reconsulta para confirmar que pegou
"""
import json
import sys
import unicodedata

from cvcrm.api import montar_corpo_nome, request
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("restaurar_nomes")


def norm(s):
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def cabecalho(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def ler_lead(idlead):
    status, body = request("GET", "/v1/comercial/leads", params={"idlead": idlead})
    leads = (body or {}).get("leads") or []
    return status, (leads[0] if leads else None), body


FONTES = [
    ("interacoes",   "/v1/comercial/leads/interacoes",  {"registros_por_pagina": 200}),
    ("conversoes",   "/v1/comercial/leads-conversao",   {"registros_por_pagina": 200}),
    ("atendimentos", "/v1/comercial/leads/atendimentos", {}),
    ("tarefas",      "/v1/comercial/leads/tarefas",     {}),
]


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    idlead = args[0]
    aplicar = "--aplicar" in args
    nome_alvo = None
    if "--nome" in args:
        nome_alvo = args[args.index("--nome") + 1].strip()

    # ---------- 1. credenciais ----------
    cabecalho("1. CREDENCIAIS")
    status, lead, body = ler_lead(idlead)
    if status == 401 or status == 403:
        raise SystemExit(f"Credenciais recusadas (HTTP {status}): {str(body)[:300]}\n"
                         "Confira dominio/email/token no config.json.")
    if status != 200:
        raise SystemExit(f"HTTP {status} ao consultar o lead: {str(body)[:400]}")
    if not lead:
        raise SystemExit(f"Lead #{idlead} nao retornou dados. "
                         "O usuario do token tem acesso a esse lead?")
    print(f"OK - autenticado, lead #{idlead} encontrado.")

    # ---------- 2. estado atual ----------
    cabecalho("2. COMO O LEAD ESTA HOJE")
    situacao = lead.get("situacao") or {}
    idsituacao = situacao.get("id") if isinstance(situacao, dict) else lead.get("idsituacao")
    print(f"  nome ....... {lead.get('nome')!r}")
    print(f"  email ...... {lead.get('email')!r}")
    print(f"  telefone ... {lead.get('telefone')!r}")
    print(f"  situacao ... {situacao.get('nome') if isinstance(situacao, dict) else situacao!r} (id {idsituacao})")
    with open(f"lead_{idlead}_antes.json", "w", encoding="utf-8") as f:
        json.dump(lead, f, ensure_ascii=False, indent=2)
    print(f"  (json completo em lead_{idlead}_antes.json)")

    # ---------- 3. caca ao nome antigo ----------
    cabecalho("3. ONDE O NOME ANTIGO AINDA EXISTE?")
    if not nome_alvo:
        print("  (rode com --nome \"Nome Antigo\" para eu marcar onde ele aparece)")
    achou_em = []
    for rotulo, caminho, extra in FONTES:
        p = {"idlead": idlead}
        p.update(extra)
        st, bd = request("GET", caminho, params=p, tentativas=1)
        txt = json.dumps(bd, ensure_ascii=False)
        marca = ""
        if nome_alvo:
            if norm(nome_alvo) in norm(txt):
                marca = "   <<<<< TEM O NOME COMPLETO"
                achou_em.append(rotulo)
            elif norm(nome_alvo.split()[0]) in norm(txt):
                marca = "   <<<<< tem o primeiro nome"
                achou_em.append(rotulo + " (parcial)")
        print(f"  [{st}] {rotulo:14s} {len(txt):>7} bytes{marca}")
        with open(f"lead_{idlead}_{rotulo}.json", "w", encoding="utf-8") as f:
            json.dump(bd, f, ensure_ascii=False, indent=2)

    if nome_alvo:
        print()
        if achou_em:
            print(f"  >> O nome sobreviveu em: {', '.join(achou_em)}")
            print("     Da para recuperar o lote automaticamente por essa fonte.")
        else:
            print("  >> O nome NAO aparece em nenhuma fonte da API v1.")
            print("     Falta testar o CVDW (python coletar.py conversoes) e, se der nada,")
            print("     o caminho e o suporte do CV ou a plataforma de origem dos leads.")

    # ---------- 4. escrita ----------
    if not aplicar:
        cabecalho("4. ESCRITA")
        print("  Nada foi alterado (faltou --aplicar).")
        if nome_alvo:
            print(f'  Para gravar: python testar_um.py {idlead} --nome "{nome_alvo}" --aplicar')
        return

    if not nome_alvo:
        raise SystemExit("--aplicar exige --nome \"Nome Que Vai Ser Gravado\"")

    cabecalho(f"4. GRAVANDO '{nome_alvo}' NO LEAD #{idlead}")
    corpo = montar_corpo_nome(idlead, nome_alvo, idsituacao,
                              email=lead.get("email"), telefone=lead.get("telefone"))
    print(f"  POST /v1/comercial/leads   headers: origemcv=true")
    print(f"  corpo: {json.dumps(corpo, ensure_ascii=False)}")
    st, resp = request("POST", "/v1/comercial/leads", corpo=corpo,
                       extra_headers={"origemcv": "true"})
    print(f"  resposta: HTTP {st} -> {json.dumps(resp, ensure_ascii=False)[:400]}")

    # ---------- 5. conferencia ----------
    cabecalho("5. CONFERINDO (releitura do lead)")
    st2, lead2, _ = ler_lead(idlead)
    nome_depois = (lead2 or {}).get("nome")
    sit2 = (lead2 or {}).get("situacao") or {}
    print(f"  nome agora .... {nome_depois!r}")
    print(f"  situacao agora  {sit2.get('nome') if isinstance(sit2, dict) else sit2!r}")
    print()
    if st not in (200, 201):
        print(f"  >> A API RECUSOU a gravacao (HTTP {st}). Nada foi alterado.")
    elif norm(nome_depois or "") == norm(nome_alvo):
        print("  >> DEU CERTO. O nome gravou. Pode seguir para o lote.")
    else:
        print("  >> NAO GRAVOU. A API respondeu OK mas o nome continua o mesmo.")
        print("     Causa provavel: o usuario do token nao e Gestor, ou o header")
        print("     origemcv nao foi aceito nesse ambiente.")
    if isinstance(situacao, dict) and isinstance(sit2, dict) and situacao.get("nome") != sit2.get("nome"):
        print(f"  >> ATENCAO: a situacao mudou de {situacao.get('nome')!r} para {sit2.get('nome')!r}")


if __name__ == "__main__":
    main()
