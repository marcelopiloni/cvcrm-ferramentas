# -*- coding: utf-8 -*-
"""Sessao autenticada no painel do CV (<dominio>.cvcrm.com.br).

Aceita duas formas de credencial, nesta ordem:
  1. curl.txt   -> cole o "Copy as cURL (bash)" de qualquer request do painel
  2. cookie.txt -> cole so o conteudo do header Cookie
"""
import gzip
import io
import os
import re
import time
import urllib.error
import urllib.request
import zlib

from cvcrm.config import RAIZ, carregar  # noqa: E402

AQUI = str(RAIZ)


def base():
    return f"https://{carregar()['dominio']}.cvcrm.com.br"

PADRAO = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

# headers que nao devem ser reaproveitados de um request para outro
IGNORAR = {"content-length", "host", "accept-encoding", "connection",
           "content-type", "referer", ":authority", ":method", ":path", ":scheme"}


def _de_curl(texto):
    """Extrai headers e cookies de um comando 'Copy as cURL'."""
    headers = {}
    for m in re.finditer(r"-H\s+'([^']+)'|-H\s+\"([^\"]+)\"", texto):
        linha = m.group(1) or m.group(2)
        if ":" not in linha:
            continue
        k, v = linha.split(":", 1)
        if k.strip().lower() not in IGNORAR:
            headers[k.strip()] = v.strip()
    for m in re.finditer(r"-b\s+'([^']+)'|--cookie\s+'([^']+)'", texto):
        headers["Cookie"] = (m.group(1) or m.group(2)).strip()
    return headers


def carregar_headers():
    curl = os.path.join(AQUI, "curl.txt")
    cook = os.path.join(AQUI, "cookie.txt")
    h = dict(PADRAO)
    if os.path.exists(curl) and os.path.getsize(curl) > 20:
        h.update(_de_curl(io.open(curl, encoding="utf-8", errors="replace").read()))
        if "Cookie" not in h:
            raise SystemExit("curl.txt nao tem cookie. Copie o cURL de um request logado.")
        return h
    if os.path.exists(cook) and os.path.getsize(cook) > 20:
        h["Cookie"] = io.open(cook, encoding="utf-8", errors="replace").read().strip()
        return h
    raise SystemExit(
        "Falta a credencial de sessao. Crie curl.txt (preferido) ou cookie.txt.\n"
        "Veja o passo a passo no LEIAME.md."
    )


HEADERS = None


def _h():
    global HEADERS
    if HEADERS is None:
        HEADERS = carregar_headers()
    return HEADERS


def decodificar(dados):
    """O painel declara utf-8 no meta mas serve cp1252. Sem isso os acentos
    dos nomes viram lixo (Joao Gonalves)."""
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("cp1252", "replace")


def _descomprimir(dados, enc):
    try:
        if enc == "gzip":
            return gzip.decompress(dados)
        if enc == "deflate":
            return zlib.decompress(dados, -zlib.MAX_WBITS)
    except Exception:
        pass
    return dados


def get(caminho, pausa=0.3, tentativas=3):
    """GET no painel. Retorna (status, texto). Detecta queda de sessao."""
    url = caminho if caminho.startswith("http") else base() + caminho
    h = dict(_h())
    h["Accept-Encoding"] = "gzip, deflate"
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=h, method="GET")
            with urllib.request.urlopen(req, timeout=60) as r:
                bruto = _descomprimir(r.read(), r.headers.get("Content-Encoding", ""))
                time.sleep(pausa)
                return r.status, decodificar(bruto)
        except urllib.error.HTTPError as e:
            bruto = _descomprimir(e.read(), e.headers.get("Content-Encoding", ""))
            if e.code in (429, 500, 502, 503, 504) and t < tentativas - 1:
                time.sleep(2 ** t * 2)
                continue
            return e.code, decodificar(bruto)
        except urllib.error.URLError as e:
            if t < tentativas - 1:
                time.sleep(2 ** t * 2)
                continue
            return 0, f"ERRO DE REDE: {e}"
    return 0, ""


def sessao_caiu(texto):
    if not texto:
        return False
    t = texto.lower()
    marcas = ["login-wrap", "form-login", "--form-wrap",
              'name="senha"', 'id="senha"', "esqueci minha senha",
              "sua sessao expirou", "sua sessão expirou", "faca login", "faça login"]
    return any(m in t for m in marcas)
