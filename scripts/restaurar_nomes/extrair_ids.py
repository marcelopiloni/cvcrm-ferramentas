# -*- coding: utf-8 -*-
"""Extrai os IDs dos leads (e contexto) do leads.xlsx colado do painel."""
import re
import sys

import pandas as pd
from cvcrm.config import usar_pasta_dados  # noqa: E402

usar_pasta_dados("restaurar_nomes")


def main():
    ARQ = sys.argv[1] if len(sys.argv) > 1 else "leads.xlsx"
    df = pd.read_excel(ARQ, dtype=str, header=None)
    grid = df.where(pd.notna(df), "").astype(str).values

    linhas = []
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            m = re.fullmatch(r"\s*#(\d{4,})\s*", grid[i][j])
            if not m:
                continue
            idlead = m.group(1)
            # janela de contexto: o cartao ocupa ~5 linhas acima do ID
            jan = []
            for k in range(max(0, i - 6), min(grid.shape[0], i + 2)):
                jan.extend(x for x in grid[k] if x.strip())
            blob = " | ".join(jan)
            data = re.search(r"Cadastrado em (\d{2}/\d{2}/\d{4})", blob)
            orig = re.search(r"Origem:\s*([^|]*)", blob)
            linhas.append({
                "idlead": idlead,
                "cadastrado_em": data.group(1) if data else "",
                "origem_planilha": (orig.group(1).strip() if orig else "").replace("\xa0", " ").strip(),
                "linha_xlsx": i + 1,
            })

    out = pd.DataFrame(linhas).drop_duplicates(subset=["idlead"])
    out = out.sort_values("idlead", key=lambda s: s.astype(int))
    out.to_csv("leads_ids.csv", index=False, encoding="utf-8-sig")
    print(f"{len(out)} leads extraidos -> leads_ids.csv")
    print(out.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
