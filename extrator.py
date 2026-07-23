"""
extrator.py — FiscoCapture
Versão Otimizada com Multiprocessamento e Detecção Seletiva.
Compatível com tabelas normais (células simples) e tabelas com cabeçalho embutido (João Pessoa).

Segurança: nenhum dado é gravado em disco. Tudo permanece em memória (lista de dicts).
"""

import re
from typing import Optional
import pdfplumber
import multiprocessing
from concurrent.futures import ProcessPoolExecutor


# ---------------------------------------------------------------------------
# Helpers de normalização e detecção
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
        "cda"
    })


def _eh_cabecalho_situacao(texto: str) -> bool:
    n = _normaliza(texto)
    return n.startswith("situa")


def _eh_cabecalho_inscricao(texto: str) -> bool:
    n = _normaliza(texto)
    return n in {"inscrição", "inscricao"}


def _split_cabecalho_valor(celula: str) -> tuple[str, str]:
    """
    Separa 'Referência\nValor' em ('Referência', 'Valor').
    Se não houver quebra de linha ou não for um cabeçalho conhecido,
    retorna ('', celula).
    """
    if not celula or "\n" not in celula:
        return ("", (celula or "").strip())
    partes = celula.split("\n", 1)
    cab_candidato = partes[0].strip()
    
    # Verifica se a primeira parte da quebra se assemelha a um cabeçalho conhecido
    if (_eh_cabecalho_referencia(cab_candidato) or 
        _eh_cabecalho_cda(cab_candidato) or 
        _eh_cabecalho_situacao(cab_candidato) or
        _eh_cabecalho_inscricao(cab_candidato)):
        return (cab_candidato, partes[1].strip())
        
    return ("", celula.strip())


# ---------------------------------------------------------------------------
# Lógica de extração de tabelas
# ---------------------------------------------------------------------------
def _extrai_tabela_hibrida(tabela: list[list], num_pagina: int) -> list[dict]:
    """
    Varre uma tabela e tenta extrair registros CDA de duas formas:
      1. Células com cabeçalho+valor embutido (João Pessoa).
      2. Tabela estruturada normal (linhas de dados abaixo do cabeçalho).
    """
    registros = []
    if not tabela or len(tabela) < 1:
        return registros

    # --- TENTATIVA 1: Procurar células embutidas 'Cabeçalho\nValor' (João Pessoa) ---
    ref_emb = cda_emb = sit_emb = ""
    for linha in tabela:
        for celula in linha:
            if not celula:
                continue
            cab, val = _split_cabecalho_valor(str(celula))
            if cab and val:
                if _eh_cabecalho_referencia(cab):
                    ref_emb = val
                elif _eh_cabecalho_cda(cab):
                    cda_emb = val
                elif _eh_cabecalho_situacao(cab):
                    sit_emb = val
    if ref_emb:
        return [{
            "pagina":    num_pagina,
            "tipo":      "CDA",
            "inscricao": "",
            "referencia": ref_emb,
            "cda":       cda_emb,
            "situacao":  sit_emb,
        }]

    # --- TENTATIVA 2: Tabela estruturada convencional (linhas normais de dados) ---
    idx_header = None
    mapa_colunas: dict[str, int] = {}

    for i, linha in enumerate(tabela):
        colunas_encontradas = {}
        for j, celula in enumerate(linha):
            if not celula:
                continue
            texto_celula = str(celula).strip()
            if _eh_cabecalho_referencia(texto_celula):
                colunas_encontradas["referencia"] = j
            elif _eh_cabecalho_cda(texto_celula):
                colunas_encontradas["cda"] = j
            elif _eh_cabecalho_situacao(texto_celula):
                colunas_encontradas["situacao"] = j
            elif _eh_cabecalho_inscricao(texto_celula):
                colunas_encontradas["inscricao"] = j

        if colunas_encontradas:
            if len(colunas_encontradas) > len(mapa_colunas):
                mapa_colunas = colunas_encontradas
                idx_header = i

    if idx_header is not None and ( "referencia" in mapa_colunas or "cda" in mapa_colunas ):
        linhas_dados = tabela[idx_header + 1:]
        for linha in linhas_dados:
            if not any(c for c in linha if c):
                continue
            
            ref = cda = sit = ins = ""
            
            if "referencia" in mapa_colunas:
                col = mapa_colunas["referencia"]
                if col < len(linha) and linha[col]:
                    ref = str(linha[col]).strip()
            if "cda" in mapa_colunas:
                col = mapa_colunas["cda"]
                if col < len(linha) and 0 <= col < len(linha) and linha[col]:
                    cda = str(linha[col]).strip()
            if "situacao" in mapa_colunas:
                col = mapa_colunas["situacao"]
                if col < len(linha) and linha[col]:
                    sit = str(linha[col]).strip()
            if "inscricao" in mapa_colunas:
                col = mapa_colunas["inscricao"]
                if col < len(linha) and linha[col]:
                    ins = str(linha[col]).strip()

            # Evita capturar nomes de cabeçalhos redundantes como dados
            if ref and _eh_cabecalho_referencia(ref):
                continue

            if ref or cda:
                registros.append({
                    "pagina":    num_pagina,
                    "tipo":      "CDA",
                    "inscricao": ins,
                    "referencia": ref,
                    "cda":       cda,
                    "situacao":  sit,
                })

    return registros


def _extrai_inscricao_tabelas(tabelas: list[list[list]], num_pagina: int) -> str:
    """
    Tenta encontrar inscrições estruturadas na página (tabelas e células).
    """
    # 1. Tenta achar células no formato 'Inscrição\n<numero>'
    for tabela in tabelas:
        for linha in tabela:
            for celula in linha:
                if not celula:
                    continue
                cab, val = _split_cabecalho_valor(str(celula))
                if cab and _eh_cabecalho_inscricao(cab) and val:
                    if not _eh_cabecalho_inscricao(val):
                        return val
                        
    # 2. Tenta achar em tabelas simples com coluna "Inscrição"
    for tabela in tabelas:
        col_ins = -1
        for i, linha in enumerate(tabela):
            for j, celula in enumerate(linha):
                if celula and _eh_cabecalho_inscricao(str(celula)):
                    col_ins = j
                    break
            if col_ins != -1:
                # Retorna a primeira linha abaixo do cabeçalho que tiver valor
                for dados_linha in tabela[i + 1:]:
                    if col_ins < len(dados_linha) and dados_linha[col_ins]:
                        v = str(dados_linha[col_ins]).strip()
                        if v and not _eh_cabecalho_inscricao(v):
                            return v
    return ""


# ---------------------------------------------------------------------------
# Processamento de Página Única
# ---------------------------------------------------------------------------
def processar_pagina_tarefa(args) -> tuple[int, list[dict], Optional[str]]:
    caminho_pdf, idx_pagina = args
    num_pagina = idx_pagina + 1
    regs_pagina = []
    aviso = None

    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            pagina = pdf.pages[idx_pagina]
            
            # Pré-filtro rápido (pula páginas em milissegundos se não houver termos chave)
            texto_inicial = pagina.extract_text(layout=False) or ""
            tem_palavras = any(p in texto_inicial for p in ["CDA", "DÍVIDA", "Inscrição", "inscrita", "Dívida", "cda", "C.D.A"])
            
            if not tem_palavras:
                return num_pagina, [], None

            tabelas = pagina.extract_tables()

            if tabelas:
                # Extrai dados da CDA usando abordagem híbrida
                for tabela in tabelas:
                    regs = _extrai_tabela_hibrida(tabela, num_pagina)
                    if regs:
                        regs_pagina.extend(regs)

                # Busca inscrição e vincula aos registros encontrados sem inscrição
                if regs_pagina:
                    inscricao = _extrai_inscricao_tabelas(tabelas, num_pagina)
                    for reg in regs_pagina:
                        if not reg["inscricao"]:
                            reg["inscricao"] = inscricao

            # Se tinha as palavras mas não achou tabelas estruturadas, avisa para auditoria
            if not regs_pagina and ("CDA" in texto_inicial or "DÍVIDA" in texto_inicial):
                aviso = f"Página {num_pagina}: Dados de CDA identificados no texto, mas nenhuma tabela de CDA estruturada pôde ser mapeada."

    except Exception as e:
        aviso = f"Erro ao processar página {num_pagina}: {str(e)}"

    return num_pagina, regs_pagina, aviso


# ---------------------------------------------------------------------------
# Função principal chamada pela interface
# ---------------------------------------------------------------------------
def extrair_dados_pdf(caminho_pdf: str) -> tuple[list[dict], list[str]]:
    registros: list[dict] = []
    avisos:    list[str]  = []

    try:
        # Tratamento de erro explícito para arquivo bloqueado no Windows
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                total_paginas = len(pdf.pages)
        except PermissionError:
            raise Exception("O arquivo PDF está aberto ou bloqueado por outro programa. Por favor, feche-o e tente novamente.")
        except Exception as e:
            raise Exception(f"Não foi possível abrir o arquivo PDF: {e}")

        tarefas = [(caminho_pdf, i) for i in range(total_paginas)]

        # Limitação segura de núcleos de CPU (evita travar RAM do usuário)
        cpus = multiprocessing.cpu_count()
        num_processos = min(cpus, total_paginas, 4)  # Máximo de 4 processos paralelos
        if num_processos < 1:
            num_processos = 1

        with ProcessPoolExecutor(max_workers=num_processos) as executor:
            resultados = list(executor.map(processar_pagina_tarefa, tarefas))

        resultados.sort(key=lambda x: x[0])

        for num_pg, regs, aviso in resultados:
            if regs:
                registros.extend(regs)
            if aviso:
                avisos.append(aviso)

    except Exception as exc:
        avisos.append(f"Erro: {exc}")

    # Pós-processamento: propaga Inscrição para linhas CDA que a sucedem na mesma página
    inscricao_por_pagina: dict[int, str] = {}
    for reg in registros:
        pg = reg["pagina"]
        if reg["inscricao"]:
            inscricao_por_pagina[pg] = reg["inscricao"]
        else:
            reg["inscricao"] = inscricao_por_pagina.get(pg, "")

    # Força a ordenação final de todos os registros pelo número da página
    registros.sort(key=lambda x: x["pagina"])

    return registros, avisos
