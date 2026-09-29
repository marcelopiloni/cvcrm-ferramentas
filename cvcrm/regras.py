# -*- coding: utf-8 -*-
"""Regras de classificacao dos leads sem nome.

Os parametros (situacoes, prazo, quem conta como integracao) vem da secao
"limpeza" do config.json.
"""
import re
from datetime import datetime

from cvcrm.config import secao

_c = secao("limpeza")
SITUACOES_PERMITIDAS = {int(k): v for k, v in _c["situacoes_descartaveis"].items()}
ID_DESCARTADO = int(_c["id_situacao_descartado"])
DIAS_INATIVIDADE = int(_c.get("dias_inatividade", 90))

VAZIOS = {"", "vazio", "sem nome", "-", "--", "none", "null"}

# autores que NAO contam como movimentacao (integracoes automaticas)
RX_INTEGRACAO = re.compile(_c.get("autores_integracao_regex") or r"(?!x)x", re.I)
RX_SISTEMA = re.compile(r"^\s*sistema\s*$", re.I)

# "Modificou o campo: X" nao e atendimento; nem eventos automaticos de fila/vencimento
RX_NAO_ATENDIMENTO = re.compile(
    r"modificou o campo|represad|foi distribu|lead vencido|lead reativado|"
    r"atendente\(s\) proveniente|lead cria", re.I)


def eh_vazio(v):
    return str(v or "").strip().lower() in VAZIOS


def autor_conta(quem):
    """True se o autor do evento e uma pessoa de verdade (nem Sistema, nem integracao)."""
    q = (quem or "").strip()
    if not q or RX_SISTEMA.match(q):
        return False
    return not RX_INTEGRACAO.search(q)


def evento_e_atendimento(quem, oque):
    """Movimentacao real = acao humana de atendimento.

    Conta: anotacao, whatsapp, e-mail, visita, tarefa, mudanca de situacao por pessoa.
    Nao conta: qualquer coisa do Sistema/integracao, e todo 'Modificou o campo'
    (inclusive Data de Vencimento e a nossa propria correcao de nome).
    """
    if not autor_conta(quem):
        return False
    return not RX_NAO_ATENDIMENTO.search(oque or "")


def parse_data(txt, hoje=None):
    """'31/08/2026 as 15:33' | 'HOJE as 11:53' | 'ONTEM as 09:10' -> datetime."""
    hoje = hoje or datetime.now()
    if not txt:
        return None
    t = txt.strip()
    hm = re.search(r"(\d{1,2}):(\d{2})", t)
    hora, minu = (int(hm.group(1)), int(hm.group(2))) if hm else (0, 0)

    if re.match(r"^\s*hoje", t, re.I):
        return hoje.replace(hour=hora, minute=minu, second=0, microsecond=0)
    if re.match(r"^\s*ontem", t, re.I):
        d = hoje.replace(hour=hora, minute=minu, second=0, microsecond=0)
        return d.replace(day=d.day - 1) if d.day > 1 else d
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", t)
    if m:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), hora, minu)
    return None


def classificar(idsituacao, eventos, nome_perdido_valor, agora=None):
    """Decide o que fazer com um lead. Retorna (acao, motivo, detalhe).

    acao: 'restaurar_nome' | 'descartar' | 'nada_a_fazer' | 'revisar'
    """
    agora = agora or datetime.now()
    try:
        sit = int(idsituacao)
    except (TypeError, ValueError):
        sit = None
    permitida = sit in SITUACOES_PERMITIDAS

    # ultima movimentacao real
    datas = [parse_data(e["quando"], agora) for e in eventos
             if evento_e_atendimento(e.get("quem"), e.get("oque"))]
    datas = [d for d in datas if d]
    ultima = max(datas) if datas else None
    dias = (agora - ultima).days if ultima else None

    # 1) regra dos 90 dias tem prioridade, so dentro das situacoes permitidas
    if permitida and (ultima is None or dias > DIAS_INATIVIDADE):
        quanto = f"{dias} dias sem atendimento" if dias is not None else "nunca teve atendimento"
        return "descartar", f"90+ dias ({quanto})", ultima

    # 2) tinha nome antes -> restaura
    if not eh_vazio(nome_perdido_valor):
        return "restaurar_nome", "tinha nome anterior", ultima

    # 3) era vazio (nao ha nome para restaurar)
    if permitida:
        return "descartar", "nome sempre vazio", ultima
    if sit == ID_DESCARTADO:
        return "nada_a_fazer", "ja esta descartado e nunca teve nome", ultima
    return "revisar", f"vazio, situacao fora da lista ({idsituacao})", ultima
