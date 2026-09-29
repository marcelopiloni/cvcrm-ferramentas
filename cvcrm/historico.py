# -*- coding: utf-8 -*-
"""Le a aba Historico do lead no painel e extrai as alteracoes do campo Nome.

  python historico.py <idlead>          # um lead, mostra na tela
  python historico.py --todos         # o lote do leads_ids.csv -> historico_nomes.csv
"""
import csv
import html as _html
import os
import re
import sys

from cvcrm.painel import get, sessao_caiu

ROTA = "/gestor/comercial/leads/{id}/historico"

RX_BLOCO = re.compile(r'<div class="linhadotempo-box(.*?)(?=<div class="linhadotempo-box|\Z)', re.S)
RX_ID = re.compile(r'linhadotempo-status">\s*#?(\d+)\s*<', re.S)
RX_QUANDO = re.compile(r'linhadotempo-quando">.*?</i>\s*(.*?)\s*</div>', re.S)
RX_QUEM = re.compile(r'linhadotempo-quem">(.*?)</div>', re.S)
RX_OQUE = re.compile(r'linhadotempo-oque">(.*?)</div>', re.S)
RX_CAMPO = re.compile(r'Modificou o campo:\s*([^<\n]+?)\s*(?:<|$)', re.S)
RX_DEPARA = re.compile(r'De:\s*<strong>(.*?)</strong>\s*para\s*<strong>(.*?)</strong>', re.S)

VAZIOS = {"", "vazio", "sem nome", "-", "--"}


def limpar(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = _html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def todos_eventos(html_txt):
    """Todos os eventos da linha do tempo, do mais novo para o mais antigo."""
    saida = []
    for m in RX_BLOCO.finditer(html_txt):
        b = m.group(1)
        ev_id = RX_ID.search(b)
        quando = RX_QUANDO.search(b)
        quem = RX_QUEM.search(b)
        oque = RX_OQUE.search(b)
        saida.append({
            "id_evento": ev_id.group(1) if ev_id else "",
            "quando": limpar(quando.group(1)) if quando else "",
            "quem": limpar(quem.group(1)) if quem else "",
            "oque": limpar(oque.group(1)) if oque else "",
        })
    return saida


def eventos_de_nome(html_txt):
    """Todos os eventos 'Modificou o campo: Nome', do mais novo para o mais velho."""
    saida = []
    for m in RX_BLOCO.finditer(html_txt):
        b = m.group(1)
        campo = RX_CAMPO.search(b)
        if not campo or limpar(campo.group(1)).lower() != "nome":
            continue
        dp = RX_DEPARA.search(b)
        if not dp:
            continue
        ev_id = RX_ID.search(b)
        quando = RX_QUANDO.search(b)
        quem = RX_QUEM.search(b)
        saida.append({
            "id_evento": ev_id.group(1) if ev_id else "",
            "quando": limpar(quando.group(1)) if quando else "",
            "quem": limpar(quem.group(1)) if quem else "",
            "de": limpar(dp.group(1)),
            "para": limpar(dp.group(2)),
        })
    return saida


def nome_perdido(eventos):
    """O nome que estava antes de virar 'Sem nome'.

    Os eventos vem do mais recente para o mais antigo. Pegamos o evento de
    apagamento mais recente (para == 'Sem nome') cujo 'de' seja um nome real.
    """
    for e in eventos:
        if e["para"].strip().lower() in VAZIOS and e["de"].strip().lower() not in VAZIOS:
            return e["de"], e
    return "", None


def buscar(idlead):
    status, txt = get(ROTA.replace("{id}", str(idlead)))
    if sessao_caiu(txt):
        raise SystemExit("\n>> SESSAO EXPIROU. Refaca o curl.txt e rode de novo.\n"
                         "   O que ja foi coletado esta salvo.")
    if status != 200 or not txt:
        return None, status
    return txt, status


def um(idlead):
    txt, status = buscar(idlead)
    if txt is None:
        print(f"#{idlead}: HTTP {status}, sem conteudo")
        return
    evs = eventos_de_nome(txt)
    print(f"#{idlead}: {len(evs)} alteracao(oes) do campo Nome\n")
    for e in evs:
        print(f"  #{e['id_evento']}  {e['quando']}")
        print(f"      {e['quem'][:70]}")
        print(f"      De: {e['de']!r}  ->  para: {e['para']!r}")
    nome, ev = nome_perdido(evs)
    print()
    print(f"  >> nome a restaurar: {nome!r}" if nome else "  >> nenhum apagamento de nome encontrado")


def todos(limite=None, saida="historico_nomes.csv"):
    with open("leads_ids.csv", encoding="utf-8-sig") as f:
        ids = [l["idlead"] for l in csv.DictReader(f)]
    if limite:
        ids = ids[:limite]

    campos = ["idlead", "nome_recuperado", "id_evento", "quando", "quem",
              "de", "para", "qtd_eventos", "obs"]
    achou = 0
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for n, i in enumerate(ids, 1):
            txt, status = buscar(i)
            if txt is None:
                w.writerow({"idlead": i, "obs": f"HTTP {status}"})
            else:
                evs = eventos_de_nome(txt)
                nome, ev = nome_perdido(evs)
                if nome:
                    achou += 1
                w.writerow({
                    "idlead": i, "nome_recuperado": nome,
                    "id_evento": (ev or {}).get("id_evento", ""),
                    "quando": (ev or {}).get("quando", ""),
                    "quem": (ev or {}).get("quem", ""),
                    "de": (ev or {}).get("de", ""),
                    "para": (ev or {}).get("para", ""),
                    "qtd_eventos": len(evs),
                    "obs": "" if nome else ("nenhum evento de nome" if not evs else "nenhum apagamento"),
                })
                f.flush()
            if n % 10 == 0 or n == len(ids):
                print(f"  {n}/{len(ids)}  (recuperados ate agora: {achou})", flush=True)
    print(f"\n-> historico_nomes.csv | {achou}/{len(ids)} nomes recuperados")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "--todos":
        lim = int(a[a.index("--limite") + 1]) if "--limite" in a else None
        todos(lim, "historico_nomes_amostra.csv" if lim else "historico_nomes.csv")
    else:
        um(a[0])
