# -*- coding: utf-8 -*-
"""Aplica o plano_limpeza.csv no CV CRM.

  python aplicar.py                              # SIMULACAO
  python aplicar.py --executar --acao descartar --limite 1
  python aplicar.py --executar                   # tudo
"""
import csv
import io
import sys
import time

from cvcrm.api import request
from cvcrm.regras import ID_DESCARTADO
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("limpeza_sem_nome")

LOG = "resultado_limpeza.csv"

# Motivo de cancelamento por situacao de ORIGEM do lead. No CV cada motivo so
# vale para certas situacoes, e o nome precisa bater EXATAMENTE com o cadastrado
# (um nome novo cria um motivo novo na base). Vem do config.json.
from cvcrm.config import secao  # noqa: E402

_lim = secao("limpeza")
MOTIVO_POR_SITUACAO = {int(k): v for k, v in _lim["motivo_por_situacao"].items()}
EXPLICACAO = _lim["explicacao_descarte"]

# leads para pular neste lote:  --pular 123,456
SEGURAR = set(sys.argv[sys.argv.index("--pular") + 1].split(",")) if "--pular" in sys.argv else set()


def corpo(l):
    """Monta o JSON. Mesmas travas da correcao de sexta."""
    c = {
        "idlead": int(l["idlead"]),
        "permitir_alteracao": True,
        "pausar_hook": True,
        "converter": False,
        "reativar_lead": False,
        "permitir_trocar_atendente": False,
        "nao_associar_gestor_corretor_imobiliaria": True,
        "ignorar_email": True,
    }
    if l["email"].strip():
        c["email"] = l["email"].strip()
    elif l["telefone"].strip():
        c["telefone"] = l["telefone"].strip()

    if l["nome_novo"].strip():
        c["nome"] = l["nome_novo"].strip()

    if l["acao"] == "descartar":
        c["idsituacao"] = ID_DESCARTADO
        sit = int(l["idsituacao"]) if str(l["idsituacao"]).strip().isdigit() else None
        motivo = MOTIVO_POR_SITUACAO.get(sit)
        if motivo:
            c["motivo_cancelamento"] = motivo
            c["descricao_motivo_cancelamento"] = EXPLICACAO
    elif str(l["idsituacao"]).strip().isdigit():
        c["idsituacao"] = int(l["idsituacao"])   # preserva a situacao atual
    return c


def main():
    executar = "--executar" in sys.argv
    limite = int(sys.argv[sys.argv.index("--limite") + 1]) if "--limite" in sys.argv else None
    filtro = sys.argv[sys.argv.index("--acao") + 1] if "--acao" in sys.argv else None
    sit_filtro = sys.argv[sys.argv.index("--situacao") + 1] if "--situacao" in sys.argv else None

    linhas = [l for l in csv.DictReader(io.open("plano_limpeza.csv", encoding="utf-8-sig"))
              if l["acao"] in ("descartar", "restaurar_nome") and l["idlead"] not in SEGURAR]
    if filtro:
        linhas = [l for l in linhas if l["acao"] == filtro]
    if sit_filtro:
        linhas = [l for l in linhas if str(l["idsituacao"]).strip() == sit_filtro]
    if limite:
        linhas = linhas[:limite]

    print(f"{'ENVIANDO' if executar else 'SIMULACAO'}: {len(linhas)} leads\n")
    log, ok = [], 0
    for n, l in enumerate(linhas, 1):
        c = corpo(l)
        if not executar:
            print(f"[{n}] #{l['idlead']} {l['acao']}: {c}")
            continue
        st, resp = request("POST", "/v1/comercial/leads", corpo=c,
                           extra_headers={"origemcv": "true"})
        bom = st in (200, 201) and (resp or {}).get("sucesso") not in (False, "false")
        ok += bom
        log.append({"idlead": l["idlead"], "acao": l["acao"], "nome": c.get("nome", ""),
                    "idsituacao_enviada": c.get("idsituacao", ""), "status": st,
                    "ok": bom, "resposta": str(resp)[:400]})
        if not bom or n <= 3 or n % 25 == 0:
            print(f"[{n}/{len(linhas)}] #{l['idlead']} {l['acao']}: "
                  f"{'OK' if bom else 'FALHOU'} ({st}) {str(resp)[:180]}", flush=True)
        time.sleep(0.4)

    if executar and log:
        with io.open(LOG, "a" if False else "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(log[0].keys()))
            w.writeheader()
            w.writerows(log)
        print(f"\n{ok}/{len(log)} aplicados. Log: {LOG}")


if __name__ == "__main__":
    main()
