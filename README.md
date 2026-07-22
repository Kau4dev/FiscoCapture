# FiscoCapture — Extrator de CDA

Extrai dados de **Certidão de Dívida Ativa (CDA)** de PDFs com texto selecionável,
exibindo todas as ocorrências de **Referência**, **Nº da C.D.A**, **Situação** e
**Inscrição** com o número da página correspondente.

> **🔒 Segurança:** nenhum dado é salvo em disco. Tudo fica apenas em memória/tela.

---

## Estrutura do projeto

```
FiscoCapture/
├── .github/
│   └── workflows/
│       └── build.yml        # Build automático do .exe via GitHub Actions
├── main.py                  # Ponto de entrada
├── extrator.py              # Lógica de extração PDF (sem I/O)
├── interface.py             # Interface gráfica tkinter
├── requirements.txt         # Dependências Python
├── setup.sh                 # Script de setup do ambiente (Linux/macOS)
├── gerar_pdf_teste.py       # Gera PDF sintético para testes
└── README.md
```

---

## Instalação e execução (Linux / macOS)

### 1. Criar o ambiente virtual (venv)

```bash
# Opção A — usar o script pronto
chmod +x setup.sh
./setup.sh

# Opção B — passo a passo manual
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> ⚠️ **Sempre use o venv** para não instalar bibliotecas no Python do sistema.

### 2. Ativar o venv (toda vez que abrir o terminal)

```bash
source .venv/bin/activate
```

### 3. Rodar a aplicação

```bash
python main.py
```

A interface gráfica abre normalmente no Linux (requer `python3-tk`).
Se não tiver, instale com: `sudo apt install python3-tk`

### 4. Testar com um PDF real

Pela interface: clique em **Abrir PDF** e selecione seu arquivo.

Pelo terminal (teste rápido sem interface):

```bash
python3 -c "
from extrator import extrair_dados_pdf
registros, avisos = extrair_dados_pdf('/caminho/para/seu_arquivo.pdf')
for r in registros:
    print(r)
"
```

### 5. (Opcional) Gerar PDF sintético para testes

```bash
pip install reportlab          # só necessário para gerar o PDF de teste
python gerar_pdf_teste.py      # cria teste_cda.pdf na pasta atual
```

---

## Gerar executável para Windows (.exe)

> **PyInstaller não faz cross-compile:** não é possível gerar um `.exe` Windows
> diretamente do Linux. Use uma das opções abaixo.

### ✅ Opção A — GitHub Actions (recomendado, gratuito)

1. Suba o projeto no GitHub
2. Vá em **Actions → Build Windows EXE → Run workflow**
3. Aguarde ~2 minutos
4. Baixe o `FiscoCapture.exe` em **Artifacts**
5. Envie o `.exe` para quem precisar — **não precisa de Python instalado**

O workflow já está configurado em [`.github/workflows/build.yml`](.github/workflows/build.yml).

### Opção B — Rodar no Windows diretamente

Se tiver acesso a uma máquina Windows com Python:

```cmd
pip install pyinstaller pdfplumber
pyinstaller --onefile --windowed --name FiscoCapture main.py
```

O `.exe` fica em `dist\FiscoCapture.exe`.

---

## Campos extraídos

| Campo       | Descrição                                  |
|-------------|---------------------------------------------|
| Pág.        | Número da página onde o dado foi encontrado |
| Inscrição   | Código de inscrição do contribuinte         |
| Referência  | Tipo de dívida (ex: IPTU - CDA, TCR - CDA) |
| Nº da C.D.A | Número da certidão de dívida ativa          |
| Situação    | Status da dívida (ex: Ativo(a))             |

---

## Estratégia de extração

1. **Detecção de tabelas** via `pdfplumber.extract_tables()` — funciona bem
   para PDFs gerados por sistema com bordas visíveis.
2. **Fallback por regex** no texto bruto — usado quando o `pdfplumber` não
   detecta tabelas (PDF com bordas invisíveis ou layout não-tabular).

Ambas as estratégias capturam **todas** as ocorrências por página.
A Inscrição é automaticamente propagada para os registros CDA que a seguem na mesma página.

---

## Requisitos

- Python 3.10+
- `pdfplumber` (instalado via `requirements.txt`)
- `tkinter` (nativo do Python — `sudo apt install python3-tk` se necessário)
- Para gerar o PDF de teste: `pip install reportlab`
- Para gerar o `.exe` no Windows: `pip install pyinstaller`
