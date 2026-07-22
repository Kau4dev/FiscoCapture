"""
extrator.py — FiscoCapture
Extrai dados de CDA (Certidão de Dívida Ativa) de PDFs com texto selecionável.

Formato real identificado (João Pessoa/PB):
  - Tabela 1: células com cabeçalho+valor na mesma célula separados por \n
              Ex: ['Referência\nIPTU - CDA (CDA)', 'Nº da C.D.A\n2024153919', 'Situação\nAtivo(a)']
  - Tabela 3 (imóvel): última coluna contém 'Inscrição\n163895-5'

Segurança: nenhum dado é gravado em disco. Tudo permanece em memória (lista de dicts).
"""

import re
from typing import Optional
import pdfplumber


# ---------------------------------------------------------------------------
# Helpers de normalização
# ---------------------------------------------------------------------------
def _normaliza(texto: str) -> str:
    return texto.strip().lower()


def _eh_cabecalho_referencia(texto: str) -> bool:
    n = _normaliza(texto)
    return n in {"referência", "referencia"}


def _eh_cabecalho_cda(texto: str) -> bool:
    n = _normaliza(texto)
    return any(n.startswith(p) for p in {
        "nº da c.d.a", "n° da c.d.a", "no da c.d.a",
        "nº da cda",   "n° da cda",   "no da cda",
        "nº cda",      "n° cda",      "no cda",
    })


def _eh_cabecalho_situacao(texto: str) -> bool:
    n = _normaliza(texto)
    return n.startswith("situa")


def _eh_cabecalho_inscricao(texto: str) -> bool:
    n = _normaliza(texto)
    return n in {"inscrição", "inscricao"}


def _split_cabecalho_valor(celula: str) -> tuple[str, str]:
    """
    Separa 'Cabeçalho\nValor' em (cabeçalho, valor).
    Retorna ('', celula) se não houver \n ou o cabeçalho não for reconhecido.
    """
    if "\n" not in celula:
        return ("", celula.strip())
    partes = celula.split("\n", 1)
    return (partes[0].strip(), partes[1].strip())


# ---------------------------------------------------------------------------
# Extração principal: formato cabeçalho\nvalor na mesma célula (Tabela 1)
# ---------------------------------------------------------------------------
def _extrai_cda_tabela_embutida(tabela: list[list], num_pagina: int) -> Optional[dict]:
    """
    Processa tabelas onde cada célula contém 'Cabeçalho\nValor'.
    Retorna um registro CDA se encontrar Referência, ou None.
    """
    ref = cda = sit = ""

    for linha in tabela:
        for celula in linha:
            if not celula:
                continue
            cab, val = _split_cabecalho_valor(str(celula))
            if not cab or not val:
                continue
            if _eh_cabecalho_referencia(cab):
                ref = val
            elif _eh_cabecalho_cda(cab):
                cda = val
            elif _eh_cabecalho_situacao(cab):
                sit = val

    if ref:
        return {
            "pagina":    num_pagina,
            "tipo":      "CDA",
            "inscricao": "",   # será preenchida depois
            "referencia": ref,
            "cda":       cda,
            "situacao":  sit,
        }
    return None


# ---------------------------------------------------------------------------
# Extração de Inscrição: procura em qualquer célula 'Inscrição\nXXXXX'
# ---------------------------------------------------------------------------
def _extrai_inscricao_tabelas(tabelas: list[list[list]], num_pagina: int) -> str:
    """
    Varre todas as tabelas da página em busca de uma célula que contenha
    'Inscrição\n<valor>' e retorna o valor encontrado (o último, se houver mais de um).
    """
    inscricao = ""
    for tabela in tabelas:
        for linha in tabela:
            for celula in linha:
                if not celula:
                    continue
                cab, val = _split_cabecalho_valor(str(celula))
                if cab and _eh_cabecalho_inscricao(cab) and val:
                    # Garante que não é só o cabeçalho repetido
                    if not _eh_cabecalho_inscricao(val):
                        inscricao = val
    return inscricao


# ---------------------------------------------------------------------------
# Extração via texto bruto (fallback)
# ---------------------------------------------------------------------------
_RE_CERTIDAO = re.compile(
    r"CERTID[ÃA]O\s+DE\s+D[ÍI]VIDA\s+ATIVA\s+"
    r"Refer[êe]ncia\s+N[º°o]\s*da\s+C\.D\.A\s+Situa[çc][ãa]o\s+"
    r"(.+?)\s+"                   # referência
    r"(\d[\d\.]+)\s+"             # nº CDA
    r"(Ativo\(a\)|Cancelado|Suspenso|[A-Za-zÀ-ú]+\([a-záàãâéèêíìîóòõôúùûç]+\))",
    re.IGNORECASE | re.DOTALL
)

_RE_INSCRICAO_TEXTO = re.compile(
    r"Inscri[çc][ãa]o\s*\n?\s*([\d\.\-/]+)",
    re.IGNORECASE
)


def _extrai_regex(pagina, num_pagina: int) -> list[dict]:
    texto = pagina.extract_text(x_tolerance=2, y_tolerance=3) or ""
    if not texto.strip():
        return []

    registros = []

    # Busca blocos "CERTIDÃO DE DÍVIDA ATIVA ... Referência ... Nº CDA ... Situação"
    for m in _RE_CERTIDAO.finditer(texto):
        ref = m.group(1).strip()
        cda = m.group(2).strip()
        sit = m.group(3).strip()

        # Inscrição: última ocorrência antes desta posição
        inscricao = ""
        for mi in _RE_INSCRICAO_TEXTO.finditer(texto[:m.start()]):
            inscricao = mi.group(1).strip()

        registros.append({
            "pagina":    num_pagina,
            "tipo":      "CDA",
            "inscricao": inscricao,
            "referencia": ref,
            "cda":       cda,
            "situacao":  sit,
        })

    if registros:
        return registros

    # Fallback mais simples: busca linha-a-linha
    linhas = texto.splitlines()
    inscricao_atual = ""
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()

        # Detecta linha de inscrição
        m_ins = _RE_INSCRICAO_TEXTO.search(linha)
        if m_ins:
            inscricao_atual = m_ins.group(1).strip()

        # Detecta linha "CERTIDÃO DE DÍVIDA ATIVA"
        if re.match(r"CERTID[ÃA]O\s+DE\s+D[ÍI]VIDA\s+ATIVA", linha, re.IGNORECASE):
            # Próxima linha deve ser: "Referência  Nº da C.D.A  Situação"
            # Linha seguinte: "<ref>  <cda>  <sit>"
            if i + 2 < len(linhas):
                linha_dados = linhas[i + 2].strip()
                # Tenta separar por múltiplos espaços
                partes = re.split(r"\s{2,}", linha_dados)
                if len(partes) >= 2:
                    ref = partes[0].strip()
                    cda = partes[1].strip() if len(partes) > 1 else ""
                    sit = partes[2].strip() if len(partes) > 2 else ""
                    if ref and not _eh_cabecalho_referencia(ref):
                        registros.append({
                            "pagina":    num_pagina,
                            "tipo":      "CDA",
                            "inscricao": inscricao_atual,
                            "referencia": ref,
                            "cda":       cda,
                            "situacao":  sit,
                        })
                        i += 3
                        continue
        i += 1

    return registros


# ---------------------------------------------------------------------------
# Função pública principal
# ---------------------------------------------------------------------------
def extrair_dados_pdf(caminho_pdf: str) -> tuple[list[dict], list[str]]:
    """
    Lê o PDF e extrai todos os registros CDA encontrados.

    Retorna:
        registros : lista de dicts com chaves pagina, tipo, inscricao,
                    referencia, cda, situacao
        avisos    : mensagens de aviso/erro por página
    """
    registros: list[dict] = []
    avisos:    list[str]  = []

    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            total_paginas = len(pdf.pages)

            for i, pagina in enumerate(pdf.pages):
                num_pagina = i + 1
                regs_pagina: list[dict] = []

                tabelas = pagina.extract_tables()

                # --- Estratégia 1: células com 'Cabeçalho\nValor' embutido ---
                if tabelas:
                    for tabela in tabelas:
                        reg = _extrai_cda_tabela_embutida(tabela, num_pagina)
                        if reg:
                            regs_pagina.append(reg)

                # --- Se achou CDAs, busca Inscrição em todas as tabelas ---
                if regs_pagina:
                    inscricao = _extrai_inscricao_tabelas(tabelas, num_pagina)
                    for reg in regs_pagina:
                        reg["inscricao"] = inscricao
                    registros.extend(regs_pagina)

                else:
                    # --- Estratégia 2: regex no texto bruto ---
                    regs_regex = _extrai_regex(pagina, num_pagina)
                    if regs_regex:
                        registros.extend(regs_regex)
                    else:
                        avisos.append(
                            f"Página {num_pagina}/{total_paginas}: "
                            "nenhum dado de CDA encontrado"
                        )

    except Exception as exc:
        avisos.append(f"Erro ao ler o PDF: {exc}")

    return registros, avisos
