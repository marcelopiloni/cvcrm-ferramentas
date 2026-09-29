# -*- coding: utf-8 -*-
"""Importa uma planilha de leads (ex.: exportacao de formulario do Meta) que nao
chegou ao CV pela integracao.

Regra: NAO entrar na roleta. Tudo vai para uma imobiliaria fixa, sem corretor,
e ela distribui. Imobiliaria, empreendimento, midia e conversao vem da secao
"importacao" do config.json.

  python -m scripts.importar_leads.importar plano                         # gera plano_importacao.csv
  python -m scripts.importar_leads.importar aplicar                       # SIMULACAO
  python -m scripts.importar_leads.importar aplicar --executar --grupo novo --limite 1
  python -m scripts.importar_leads.importar aplicar --executar
"""
import csv
import io
import re
import sys
import time

import pandas as pd

from scripts.importar_leads.checar_duplicados import ARQ, normalizar_tel
from cvcrm.api import request
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("importar_leads")

from cvcrm.config import secao  # noqa: E402

_imp = secao("importacao")
ID_IMOBILIARIA = int(_imp["idimobiliaria"])
ID_EMPREENDIMENTO = int(_imp["idempreendimento"])
ID_ENTRADA = int(_imp.get("id_situacao_entrada", 1))
CONVERSAO = _imp["conversao"]
ORIGEM = _imp.get("origem", "FB")
IDMIDIA = int(_imp["idmidia"]) if _imp.get("idmidia") else None
SITS_REATIVAVEIS = {str(x) for x in _imp.get("situacoes_reativaveis", [3])}

EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")

SEM_ROLETA = {
    "idimobiliaria": ID_IMOBILIARIA,
    "lead_utilizar_fila": False,
    "utilizar_fila_gestor": False,
    "utilizar_fila_corretor": False,
    "forcar_distribuicao_lead": False,
    "permitir_trocar_atendente": True,   # precisa trocar para a imobiliaria de destino
}


def limpar_nome(n):
    return re.sub(r"\s+", " ", EMOJI.sub("", n or "")).strip()[:100] or "Sem nome"


def escolher_para_reativar(confirmados_txt, ids, sits):
    """Entre os leads confirmados da mesma pessoa, qual reativar."""
    ids = [i for i in ids.split(";") if i]
    sits = sits.split(";")
    pares = list(zip(ids, sits, confirmados_txt.split(" | ")))
    # prioridade: email+telefone > email > telefone; depois o id mais novo
    def peso(p):
        t = p[2]
        return (2 if "email+telefone" in t else 1 if "por email" in t else 0, int(p[0]))
    return max(pares, key=peso)[0]


def plano():
    dup = list(csv.DictReader(io.open("duplicados.csv", encoding="utf-8-sig")))
    out = []
    for d in dup:
        ids = [i for i in d["ids"].split(";") if i]
        sits = [s for s in d["situacoes"].split(";") if s]
        base = {"linha": d["linha"], "nome": limpar_nome(d["full_name"]),
                "nome_original": d["full_name"], "email": d["email"],
                "telefone": d["phone_normalizado"], "telefone_original": d["phone_original"],
                "leads_no_cv": d["confirmados"]}
        if not ids:
            out.append({**base, "grupo": "novo", "idlead": "", "motivo": "nao existe no CV"})
        elif any(s not in SITS_REATIVAVEIS for s in sits):
            out.append({**base, "grupo": "nao_tocar", "idlead": d["ids"],
                        "motivo": "ha lead ativo dessa pessoa (atendimento/analise/reserva/venda)"})
        else:
            alvo = escolher_para_reativar(d["confirmados"], d["ids"], d["situacoes"])
            out.append({**base, "grupo": "reativar", "idlead": alvo,
                        "motivo": f"todos os {len(ids)} registros em DESCARTADO/VENCIDO"})
    with io.open("plano_importacao.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    import collections
    print("-> plano_importacao.csv")
    for k, v in collections.Counter(x["grupo"] for x in out).most_common():
        print(f"   {k:10} {v}")
    print(f"   nomes alterados na limpeza: {sum(1 for x in out if x['nome'] != x['nome_original'].strip())}")
    print(f"   sem telefone valido (vai so com email): {sum(1 for x in out if not x['telefone'])}")


def corpo(l):
    c = {"nome": l["nome"], "email": l["email"], "origem": ORIGEM,
         "idempreendimento": [ID_EMPREENDIMENTO], "conversao": CONVERSAO,
         "idsituacao": ID_ENTRADA, **SEM_ROLETA}
    if l["telefone"]:
        c["telefone"] = l["telefone"]
    if IDMIDIA:
        c["idmidia"] = IDMIDIA
    if l["grupo"] == "reativar":
        # Na reativacao o CV grava "Sem nome" se o campo nome nao vier.
        # Entao relemos o lead e reenviamos o nome que ele ja tem.
        st, b = request("GET", "/v1/comercial/leads", params={"idlead": l["idlead"]})
        atual = (((b or {}).get("leads") or [{}])[0].get("nome") or "").strip()
        if atual and atual.lower() not in ("sem nome", "vazio"):
            c["nome"] = atual
        c.update({"idlead": int(l["idlead"]), "permitir_alteracao": True,
                  "reativar_lead": True,
                  "remover_corretor": True})   # a imobiliaria distribui, sem corretor herdado
    return c


def aplicar():
    executar = "--executar" in sys.argv
    lim = int(sys.argv[sys.argv.index("--limite") + 1]) if "--limite" in sys.argv else None
    grupo = sys.argv[sys.argv.index("--grupo") + 1] if "--grupo" in sys.argv else None
    linhas = [l for l in csv.DictReader(io.open("plano_importacao.csv", encoding="utf-8-sig"))
              if l["grupo"] in ("novo", "reativar") and (not grupo or l["grupo"] == grupo)]
    try:
        feitos = {l["linha"] for l in csv.DictReader(io.open("resultado_importacao.csv", encoding="utf-8-sig"))
                  if l["ok"] == "True"}
    except FileNotFoundError:
        feitos = set()
    linhas = [l for l in linhas if l["linha"] not in feitos]
    if lim:
        linhas = linhas[:lim]
    print(f"{'ENVIANDO' if executar else 'SIMULACAO'}: {len(linhas)} leads ({len(feitos)} ja feitos antes)\n")

    novo_arquivo = not feitos
    f = io.open("resultado_importacao.csv", "w" if novo_arquivo else "a", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(f, fieldnames=["linha", "grupo", "idlead", "email", "status", "ok", "resposta"])
    if novo_arquivo and executar:
        w.writeheader()
    ok = 0
    for n, l in enumerate(linhas, 1):
        c = corpo(l)
        if not executar:
            print(f"[{n}] linha {l['linha']} {l['grupo']}: {c}")
            continue
        st, r = request("POST", "/v1/comercial/leads", corpo=c, extra_headers={"origemcv": "true"})
        bom = st in (200, 201) and (r or {}).get("sucesso") not in (False, "false")
        ok += bom
        w.writerow({"linha": l["linha"], "grupo": l["grupo"],
                    "idlead": (r or {}).get("id", l["idlead"]), "email": l["email"],
                    "status": st, "ok": bom, "resposta": str(r)[:400]})
        f.flush()
        print(f"[{n}/{len(linhas)}] linha {l['linha']} {l['grupo']} -> "
              f"{'OK' if bom else 'FALHOU'} ({st}) id={(r or {}).get('id')} "
              f"corretor={(r or {}).get('idcorretor')} imob={(r or {}).get('idimobiliaria')}", flush=True)
        time.sleep(0.4)
    f.close()
    if executar:
        print(f"\n{ok}/{len(linhas)} OK -> resultado_importacao.csv")


if __name__ == "__main__":
    {"plano": plano, "aplicar": aplicar}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
