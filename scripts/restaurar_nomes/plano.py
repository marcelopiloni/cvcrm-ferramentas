# -*- coding: utf-8 -*-
"""Cruza leads_atual.csv (estado hoje) com historico_nomes.csv (nome perdido)
e gera plano_correcao.csv para conferencia humana antes de gravar."""
import csv
import io
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("restaurar_nomes")

SEM_NOME = {"", "sem nome", "-", "--", "vazio", "none", "null"}


def eh_vazio(n):
    return str(n or "").strip().lower() in SEM_NOME


def ler(caminho):
    return list(csv.DictReader(io.open(caminho, encoding="utf-8-sig")))


def main():
    atuais = {str(a["idlead"]): a for a in ler("leads_atual.csv")}
    hist = {str(h["idlead"]): h for h in ler("historico_nomes.csv")}

    linhas = []
    for i, a in atuais.items():
        h = hist.get(i, {})
        recuperado = (h.get("nome_recuperado") or "").strip()
        atual = (a.get("nome_atual") or "").strip()
        email = (a.get("email") or "").strip()
        telefone = (a.get("telefone") or "").strip()

        motivo = ""
        if not recuperado:
            motivo = "sem nome no historico"
        elif not eh_vazio(atual):
            motivo = f"lead ja tem nome ({atual}) - nao mexer"
        elif not email and not telefone:
            motivo = "sem email e sem telefone - a API recusa a edicao"
        elif atual.startswith("<ERRO"):
            motivo = "falha ao ler o lead"

        linhas.append({
            "idlead": i,
            "nome_atual": atual,
            "nome_novo": recuperado if not motivo else "",
            "aplicar": "S" if not motivo else "N",
            "motivo_nao": motivo,
            "apagado_em": h.get("quando", ""),
            "apagado_por": (h.get("quem") or "")[:60],
            "email": email,
            "telefone": telefone,
            "idsituacao": a.get("idsituacao", ""),
            "situacao": a.get("situacao", ""),
        })

    linhas.sort(key=lambda l: (l["aplicar"] != "S", int(l["idlead"])))
    campos = ["idlead", "nome_atual", "nome_novo", "aplicar", "motivo_nao",
              "apagado_em", "apagado_por", "email", "telefone", "idsituacao", "situacao"]
    with io.open("plano_correcao.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    prontos = [l for l in linhas if l["aplicar"] == "S"]
    fora = [l for l in linhas if l["aplicar"] != "S"]
    print(f"-> plano_correcao.csv | {len(linhas)} leads")
    print(f"   {len(prontos)} prontos para gravar (aplicar=S)")
    print(f"   {len(fora)} fora")
    for l in fora:
        print(f"      #{l['idlead']}: {l['motivo_nao']}")
    print()
    print("   amostra do que sera gravado:")
    for l in prontos[:8]:
        print(f"      #{l['idlead']:<8} '{l['nome_atual']}' -> '{l['nome_novo']}'")


if __name__ == "__main__":
    main()
