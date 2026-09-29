# -*- coding: utf-8 -*-
"""Cliente minimo da API do CV CRM (v1 + CVDW) com retry e rate-limit."""
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from cvcrm.config import CONFIG as CFG_PATH  # noqa: E402


def carregar_config():
    from cvcrm.config import carregar
    return carregar()


CFG = None
PAUSA = float(os.environ.get("CV_PAUSA", "0.4"))


def _cfg():
    global CFG
    if CFG is None:
        CFG = carregar_config()
    return CFG


def _base(cvdw):
    c = _cfg()
    return f"https://{c['dominio']}.cvcrm.com.br/api" + ("/v1/cvdw" if cvdw else "")


def request(metodo, caminho, params=None, corpo=None, cvdw=False, extra_headers=None,
            tentativas=4):
    c = _cfg()
    url = _base(cvdw) + caminho
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    headers = {
        "email": c["email"],
        "token": c["token"],
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(corpo, ensure_ascii=False).encode("utf-8") if corpo is not None else None

    ultimo = None
    for t in range(tentativas):
        req = urllib.request.Request(url, data=data, headers=headers, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                bruto = r.read().decode("utf-8", "replace")
                time.sleep(PAUSA)
                try:
                    return r.status, json.loads(bruto)
                except json.JSONDecodeError:
                    return r.status, {"_bruto": bruto[:2000]}
        except urllib.error.HTTPError as e:
            bruto = e.read().decode("utf-8", "replace")
            try:
                corpo_erro = json.loads(bruto)
            except json.JSONDecodeError:
                corpo_erro = {"_bruto": bruto[:2000]}
            ultimo = (e.code, corpo_erro)
            if e.code in (429, 500, 502, 503, 504) and t < tentativas - 1:
                time.sleep(2 ** t * 2)
                continue
            return ultimo
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            # ConnectionResetError, timeout, RemoteDisconnected, IncompleteRead...
            ultimo = (0, {"erro_rede": f"{type(e).__name__}: {e}"})
            if t < tentativas - 1:
                time.sleep(2 ** t * 3)
                continue
            return ultimo
    return ultimo


def paginar_cvdw(caminho, por_pagina=500, params=None, limite_paginas=None, verboso=True):
    """Itera todos os registros de um endpoint CVDW."""
    pagina = 1
    while True:
        p = dict(params or {})
        p.update({"pagina": pagina, "registros_por_pagina": por_pagina})
        status, body = request("GET", caminho, params=p, cvdw=True, tentativas=6)
        if status != 200 or not isinstance(body, dict):
            print(f"  [!] pagina {pagina} falhou: HTTP {status} {str(body)[:200]}")
            print("      esperando 30s e tentando a mesma pagina de novo...")
            time.sleep(30)
            status, body = request("GET", caminho, params=p, cvdw=True, tentativas=6)
            if status != 200 or not isinstance(body, dict):
                print(f"  [!] pagina {pagina} falhou de novo. Parando aqui.")
                return
        dados = body.get("dados") or []
        total_pag = int(body.get("total_de_paginas") or 1)
        if verboso:
            print(f"  pagina {pagina}/{total_pag} ({len(dados)} registros)", flush=True)
        for d in dados:
            yield d
        if pagina >= total_pag or not dados:
            return
        if limite_paginas and pagina >= limite_paginas:
            return
        pagina += 1


def montar_corpo_nome(idlead, nome, idsituacao=None, email=None, telefone=None):
    """Corpo minimo e blindado para SO corrigir o nome de um lead existente.

    As travas vem da doc do POST /v1/comercial/leads e existem para a correcao
    nao disparar efeito colateral nenhum:
      pausar_hook ............. nao dispara webhook (senao a integracao de origem
                                recebe a alteracao de volta)
      converter ............... nao registra uma nova conversao no lead
      reativar_lead ........... nao reativa lead perdido/cancelado
      permitir_trocar_atendente  mantem gestor/corretor/imobiliaria
      nao_associar_gestor_... . idem, reforco
      ignorar_email ........... nao dispara e-mail de cadastro para ninguem
      idsituacao .............. reenviado para a situacao nao se mexer

    email/telefone sao obrigatorios pela API mesmo em edicao (erro
    'email_telefone_vazio'). Reenviamos o valor que o lead ja tem, entao nao
    muda nada — so satisfaz a validacao.
    """
    corpo = {
        "idlead": int(idlead),
        "permitir_alteracao": True,
        "nome": nome,
        "pausar_hook": True,
        "converter": False,
        "reativar_lead": False,
        "permitir_trocar_atendente": False,
        "nao_associar_gestor_corretor_imobiliaria": True,
        "ignorar_email": True,
    }
    if str(idsituacao or "").strip().isdigit():
        corpo["idsituacao"] = int(idsituacao)
    if str(email or "").strip():
        corpo["email"] = str(email).strip()
    if str(telefone or "").strip():
        corpo["telefone"] = str(telefone).strip()
    if "email" not in corpo and "telefone" not in corpo:
        raise ValueError(f"lead {idlead}: sem email nem telefone, a API recusa a edicao")
    return corpo
