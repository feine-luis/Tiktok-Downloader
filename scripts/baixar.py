#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le em uma planilha do Google Sheets (publicada como CSV) a lista de TikToks
a baixar, baixa apenas os que ainda nao foram baixados, e salva em ./out.

Roda dentro do GitHub Actions. Nao precisa de nada instalado na sua maquina.

Variaveis de ambiente:
    SHEET_CSV_URL    (obrigatoria) URL do CSV publicado do Google Sheets
    TIKTOK_COOKIES   (opcional)    conteudo de um cookies.txt do TikTok
"""

import csv
import io
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# CONFIGURACAO - ajuste os nomes das colunas conforme a sua planilha
# ---------------------------------------------------------------------------

# Coluna com o link. O script ignora acentos, maiusculas e espacos ao comparar,
# entao "Link do vídeo (TikTok)" e "link do video (tiktok)" dao no mesmo.
COLUNAS_URL = [
    "Link do vídeo (TikTok)",
    "link do video",
    "link",
    "url",
]

# Colunas usadas para nomear o arquivo, NESTA ordem.
# Resultado: @mariasilva__colageno__MARIA10__7391234567.mp4
# Para mudar a ordem ou tirar/por campos, basta editar esta lista.
COLUNAS_NOME = [
    "@TikTok",
    "Produto",
    "Cupom",
]

# Colunas que indicam que o video JA foi subido como anuncio.
# Se qualquer uma delas estiver marcada, o download e pulado.
COLUNAS_JA_SUBIDO = [
    "Perfil LM",
    "Perfil Dark",
    "Perfil da criadora",
]

# Valores que contam como "ja subido" nas colunas acima.
# A comparacao ignora acento, maiuscula e espaco em branco.
VALORES_SIM = ["sim", "s", "x", "ok", "feito", "subido"]

# Segundos de pausa entre downloads. Nao abaixe muito: o TikTok limita.
PAUSA = 3.0

# Marca d'agua do TikTok.
#   False = baixa limpo, sem o logo (padrao)
#   True  = mantem o logo e o @ da criadora no video
# Anuncios com cara de conteudo organico as vezes performam melhor COM o logo.
# Se quiser testar as duas versoes, rode uma vez com cada valor.
MANTER_MARCA_DAGUA = False

# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "out"
MANIFESTO = RAIZ / "baixados.txt"
RELATORIO = RAIZ / "ultimo_relatorio.md"


def slug(texto, limite=40):
    texto = unicodedata.normalize("NFKD", str(texto).strip())
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    return re.sub(r"[\s_-]+", "_", texto)[:limite]


def id_do_video(url):
    m = re.search(r"/video/(\d+)", url) or re.search(r"(\d{15,25})", url)
    return m.group(1) if m else slug(url, 24)


def baixar_planilha(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    r.encoding = "utf-8"
    linhas = list(csv.DictReader(io.StringIO(r.text)))
    if not linhas:
        sys.exit("[ERRO] A planilha veio vazia. Confira se ela esta publicada como CSV.")
    return linhas


def normalizar(texto):
    """'Link do vídeo (TikTok)' -> 'linkdovideotiktok' (para comparar cabecalhos)."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def achar_coluna(cabecalho, candidatas):
    mapa = {normalizar(c): c for c in cabecalho if c}
    # 1a passada: correspondencia exata
    for cand in candidatas:
        if normalizar(cand) in mapa:
            return mapa[normalizar(cand)]
    # 2a passada: correspondencia parcial (o cabecalho contem o candidato)
    for cand in candidatas:
        alvo = normalizar(cand)
        for chave, original in mapa.items():
            if alvo and alvo in chave:
                return original
    return None


def preparar_cookies():
    conteudo = os.environ.get("TIKTOK_COOKIES", "").strip()
    if not conteudo:
        return None
    caminho = RAIZ / "cookies.txt"
    caminho.write_text(conteudo + "\n", encoding="utf-8")
    print("Usando cookies do TikTok (secret configurado).")
    return str(caminho)


def baixar_video(url, destino_sem_extensao, cookies):
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    if MANTER_MARCA_DAGUA:
        # O formato de id "download" e a versao com o logo do TikTok queimado.
        formato = "b[format_id*=download]/b"
    else:
        formato = "bv*[format_id!*=download]+ba/b[format_id!*=download]/b"

    opts = {
        "format": formato,
        "merge_output_format": "mp4",
        "outtmpl": str(destino_sem_extensao) + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 5,
        "fragment_retries": 5,
    }
    if cookies:
        opts["cookiefile"] = cookies

    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        return True, ""
    except DownloadError as e:
        return False, str(e).splitlines()[0][:180]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:180]


def main():
    sheet_url = os.environ.get("SHEET_CSV_URL", "").strip()
    if not sheet_url:
        sys.exit("[ERRO] Falta o secret SHEET_CSV_URL. Veja o README.")

    SAIDA.mkdir(exist_ok=True)
    linhas = baixar_planilha(sheet_url)
    cabecalho = list(linhas[0].keys())

    col_url = achar_coluna(cabecalho, COLUNAS_URL)
    if not col_url:
        sys.exit(
            f"[ERRO] Nao achei a coluna de links.\n"
            f"       Colunas encontradas: {cabecalho}\n"
            f"       Ajuste COLUNAS_URL no topo de scripts/baixar.py"
        )

    cols_nome = [c for c in (achar_coluna(cabecalho, [n]) for n in COLUNAS_NOME) if c]
    cols_nome = list(dict.fromkeys(cols_nome))

    cols_subido = [c for c in (achar_coluna(cabecalho, [n]) for n in COLUNAS_JA_SUBIDO) if c]
    cols_subido = list(dict.fromkeys(cols_subido))
    valores_sim = {normalizar(v) for v in VALORES_SIM}

    ja_baixados = set()
    if MANIFESTO.exists():
        ja_baixados = {l.strip() for l in MANIFESTO.read_text(encoding="utf-8").splitlines() if l.strip()}

    cookies = preparar_cookies()

    print(f"Planilha  : {len(linhas)} linhas")
    print(f"Coluna URL: {col_url}")
    print(f"Nome      : {' + '.join(cols_nome) or '(so o ID)'} + ID")
    print(f"Ja subido : {' / '.join(cols_subido) or '(nenhuma coluna encontrada)'}")
    print(f"Ja no historico: {len(ja_baixados)}\n")

    novos, falhas, pulados, ignorados, ja_subidos = [], [], 0, [], 0

    for i, linha in enumerate(linhas, start=2):
        url = (linha.get(col_url) or "").strip()
        if not url:
            continue

        # Varias linhas da planilha vem sem "https://" na frente.
        # Sem isso o script pularia essas linhas em silencio.
        if not url.lower().startswith("http"):
            url = "https://" + url.lstrip("/")

        # Links que nao sao do TikTok (Instagram, YouTube) sao separados:
        # eles quase sempre exigem login e falhariam com erro confuso.
        if "tiktok.com" not in url.lower():
            ignorados.append({"linha": i, "url": url})
            continue

        # Se ja foi subido em algum dos perfis, nao precisa baixar.
        if any(normalizar(linha.get(c) or "") in valores_sim for c in cols_subido):
            ja_subidos += 1
            continue

        vid = id_do_video(url)
        if vid in ja_baixados:
            pulados += 1
            continue

        partes = [slug(linha[c]) for c in cols_nome if (linha.get(c) or "").strip().lower() not in ("", "nan")]
        nome = "__".join(partes + [vid])

        print(f"linha {i:>4} | {nome} ... ", end="", flush=True)
        ok, erro = baixar_video(url, SAIDA / nome, cookies)

        if ok:
            print("OK")
            novos.append(vid)
        else:
            print(f"FALHOU: {erro}")
            falhas.append({"linha": i, "url": url, "erro": erro})

        time.sleep(PAUSA)

    if novos:
        with MANIFESTO.open("a", encoding="utf-8") as f:
            f.writelines(v + "\n" for v in novos)

    # Relatorio legivel, commitado no repo a cada execucao
    rel = [
        f"# Ultima execucao\n",
        f"- Baixados agora: **{len(novos)}**",
        f"- Ja subidos como anuncio (pulados): {ja_subidos}",
        f"- Ja estavam baixados (pulados): {pulados}",
        f"- Falhas: **{len(falhas)}**\n",
    ]
    if falhas:
        rel.append("## Linhas que falharam\n")
        rel.append("| Linha | Link | Erro |")
        rel.append("|---|---|---|")
        for f_ in falhas:
            rel.append(f"| {f_['linha']} | {f_['url']} | {f_['erro'].replace('|', '/')} |")
        rel.append("\nRode o workflow de novo para tentar essas linhas outra vez.")

    if ignorados:
        rel.append("\n## Links que nao sao do TikTok (baixe na mao)\n")
        rel.append("| Linha | Link |")
        rel.append("|---|---|")
        for g in ignorados:
            rel.append(f"| {g['linha']} | {g['url']} |")

    RELATORIO.write_text("\n".join(rel) + "\n", encoding="utf-8")

    print(f"\n{'-'*52}")
    print(f"Baixados: {len(novos)} | Ja subidos: {ja_subidos} | Ja baixados: {pulados} | Falhas: {len(falhas)} | Nao-TikTok: {len(ignorados)}")

    # Nao derruba o job por falhas parciais: o relatorio ja registra.
    if novos == [] and falhas:
        print("\nAVISO: nenhum video baixado nesta execucao.")


if __name__ == "__main__":
    main()
