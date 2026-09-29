# -*- coding: utf-8 -*-
"""Le a aba Historico no painel e recupera o nome que foi apagado.

  python -m scripts.restaurar_nomes.historico_nomes <idlead>
  python -m scripts.restaurar_nomes.historico_nomes --todos [--limite N]
"""
import sys

from cvcrm.config import usar_pasta_dados
from cvcrm.historico import todos, um

usar_pasta_dados("restaurar_nomes")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "--todos":
        lim = int(a[a.index("--limite") + 1]) if "--limite" in a else None
        todos(lim, "historico_nomes_amostra.csv" if lim else "historico_nomes.csv")
    else:
        um(a[0])
