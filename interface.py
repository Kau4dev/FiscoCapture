"""
interface.py — FiscoCapture
Interface gráfica com tkinter. Todos os dados ficam apenas em memória/tela.
Suporta cópia rápida de valores da tabela.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import sys
import os

from extrator import extrair_dados_pdf


# ---------------------------------------------------------------------------
# Paleta de cores
# ---------------------------------------------------------------------------
COR_FUNDO       = "#1e2130"
COR_PAINEL      = "#252a3d"
COR_BORDA       = "#3a4060"
COR_DESTAQUE    = "#4f7cff"
COR_DESTAQUE2   = "#7c4fff"
COR_TEXTO       = "#e8eaf0"
COR_TEXTO_FRACO = "#8892b0"
COR_SUCESSO     = "#43d9ad"
COR_AVISO       = "#f7c948"
COR_ERRO        = "#ff6b6b"
COR_LINHA_PAR   = "#1a1e2e"
COR_LINHA_IMPAR = "#252a3d"

FONTE_TITULO = ("Segoe UI", 15, "bold")
FONTE_LABEL  = ("Segoe UI", 10)
FONTE_MONO   = ("Consolas", 9)
FONTE_TABELA = ("Segoe UI", 9)


# ---------------------------------------------------------------------------
# Aplicação principal
# ---------------------------------------------------------------------------
class FiscoCaptureApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FiscoCapture — Extrator de CDA")
        self.geometry("1100x720")
        self.minsize(900, 580)
        self.configure(bg=COR_FUNDO)
        self.resizable(True, True)

        # Estado interno
        self._caminho_pdf = tk.StringVar(value="Nenhum arquivo selecionado")
        self._processando  = False
        self._registros:   list[dict] = []
        self._filtrando_duplicados = False

        # Tratamento de saída limpa
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self._constroi_ui()
        self._centraliza()
        self._cria_menu_contexto()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _constroi_ui(self):
        # --- Cabeçalho ---
        hdr = tk.Frame(self, bg=COR_PAINEL, height=70)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Label(
            hdr, text="🔍  FiscoCapture", font=FONTE_TITULO,
            fg=COR_DESTAQUE, bg=COR_PAINEL, padx=20
        ).pack(side="left", pady=15)

        tk.Label(
            hdr, text="Extrator de Certidão de Dívida Ativa",
            font=("Segoe UI", 10), fg=COR_TEXTO_FRACO, bg=COR_PAINEL
        ).pack(side="left", pady=15)

        # Aviso de segurança
        tk.Label(
            hdr,
            text="🔒  Dados em tela — Dê duplo clique para copiar valores",
            font=("Segoe UI", 9), fg=COR_SUCESSO, bg=COR_PAINEL, padx=20
        ).pack(side="right", pady=15)

        # --- Área de seleção de arquivo ---
        sel = tk.Frame(self, bg=COR_FUNDO, pady=14, padx=20)
        sel.pack(fill="x")

        tk.Label(sel, text="Arquivo PDF:", font=FONTE_LABEL,
                 fg=COR_TEXTO, bg=COR_FUNDO).grid(row=0, column=0, sticky="w")

        entry = tk.Entry(
            sel, textvariable=self._caminho_pdf,
            font=FONTE_MONO, bg=COR_PAINEL, fg=COR_TEXTO,
            relief="flat", bd=5, state="readonly",
            readonlybackground=COR_PAINEL,
            insertbackground=COR_TEXTO
        )
        entry.grid(row=0, column=1, sticky="ew", padx=10)

        btn_abrir = tk.Button(
            sel, text="📂  Abrir PDF", command=self._selecionar_pdf,
            bg=COR_DESTAQUE, fg="white", font=FONTE_LABEL,
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground=COR_DESTAQUE2, activeforeground="white"
        )
        btn_abrir.grid(row=0, column=2, padx=(0, 8))

        self._btn_processar = tk.Button(
            sel, text="▶  Processar", command=self._iniciar_processamento,
            bg="#2ecc71", fg="white", font=FONTE_LABEL,
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#27ae60", activeforeground="white",
            state="disabled"
        )
        self._btn_processar.grid(row=0, column=3, padx=(0, 8))

        btn_limpar = tk.Button(
            sel, text="🗑  Limpar", command=self._limpar,
            bg=COR_BORDA, fg=COR_TEXTO, font=FONTE_LABEL,
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground=COR_DESTAQUE, activeforeground="white"
        )
        btn_limpar.grid(row=0, column=4)

        sel.columnconfigure(1, weight=1)

        # --- Ações Secundárias (Copiar / Filtrar) ---
        act = tk.Frame(self, bg=COR_FUNDO, padx=20)
        act.pack(fill="x", pady=(0, 10))

        self._btn_copiar_tudo = tk.Button(
            act, text="📋  Copiar Todos os Resultados", command=self._copiar_tudo,
            bg=COR_BORDA, fg=COR_TEXTO, font=FONTE_LABEL,
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground=COR_DESTAQUE, activeforeground="white",
            state="disabled"
        )
        self._btn_copiar_tudo.pack(side="left", padx=(0, 8))

        self._btn_filtra_duplicados = tk.Button(
            act, text="🔍  Remover Duplicados", command=self._toggle_duplicados,
            bg=COR_BORDA, fg=COR_TEXTO, font=FONTE_LABEL,
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground=COR_DESTAQUE, activeforeground="white",
            state="disabled"
        )
        self._btn_filtra_duplicados.pack(side="left")

        # --- Barra de progresso ---
        self._progresso = ttk.Progressbar(
            self, mode="indeterminate", style="TProgressbar"
        )
        self._progresso.pack(fill="x", padx=20)

        # --- Estatísticas ---
        stats = tk.Frame(self, bg=COR_FUNDO, padx=20, pady=6)
        stats.pack(fill="x")

        self._lbl_total   = self._badge(stats, "Registros: —", COR_DESTAQUE,  0)
        self._lbl_paginas = self._badge(stats, "Páginas: —",   COR_DESTAQUE2, 1)
        self._lbl_avisos  = self._badge(stats, "Avisos: —",    COR_AVISO,     2)

        # --- Notebook: Tabela de resultados + Log de avisos ---
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Aba Resultados
        aba_res = tk.Frame(nb, bg=COR_FUNDO)
        nb.add(aba_res, text="  Resultados  ")
        self._constroi_tabela(aba_res)

        # Aba Avisos/Debug
        aba_log = tk.Frame(nb, bg=COR_FUNDO)
        nb.add(aba_log, text="  Log / Avisos  ")
        self._constroi_log(aba_log)

        # Estilos ttk
        self._aplica_estilos()

    def _badge(self, parent, texto, cor, col):
        frm = tk.Frame(parent, bg=cor, padx=8, pady=3)
        frm.grid(row=0, column=col, padx=(0, 8))
        lbl = tk.Label(frm, text=texto, font=("Segoe UI", 9, "bold"),
                       fg="white", bg=cor)
        lbl.pack()
        return lbl

    def _constroi_tabela(self, parent):
        colunas = ("pagina", "inscricao", "referencia", "cda", "situacao")
        self.colunas = colunas
        cabecalhos = {
            "pagina":    "Pág.",
            "inscricao": "Inscrição (Duplo clique copia)",
            "referencia":"Referência",
            "cda":       "Nº da C.D.A (Duplo clique copia)",
            "situacao":  "Situação",
        }
        larguras = {
            "pagina": 50, "inscricao": 200, "referencia": 260,
            "cda": 220, "situacao": 120
        }

        frame = tk.Frame(parent, bg=COR_FUNDO)
        frame.pack(fill="both", expand=True)

        self._tree = ttk.Treeview(
            frame, columns=colunas, show="headings",
            style="Custom.Treeview"
        )

        for col in colunas:
            self._tree.heading(col, text=cabecalhos[col])
            self._tree.column(col, width=larguras[col],
                              minwidth=40, anchor="center")

        # Scrollbars
        sb_v = ttk.Scrollbar(frame, orient="vertical",
                             command=self._tree.yview)
        sb_h = ttk.Scrollbar(frame, orient="horizontal",
                             command=self._tree.xview)
        self._tree.configure(yscrollcommand=sb_v.set,
                              xscrollcommand=sb_h.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        sb_v.grid(row=0, column=1, sticky="ns")
        sb_h.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # Tags de cor alternada
        self._tree.tag_configure("par",   background=COR_LINHA_PAR,
                                           foreground=COR_TEXTO)
        self._tree.tag_configure("impar", background=COR_LINHA_IMPAR,
                                           foreground=COR_TEXTO)
        
        # Interações de cópia
        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<Button-3>", self._on_right_click)

    def _constroi_log(self, parent):
        frame = tk.Frame(parent, bg=COR_FUNDO)
        frame.pack(fill="both", expand=True)

        self._txt_log = tk.Text(
            frame, bg=COR_PAINEL, fg=COR_TEXTO_FRACO,
            font=FONTE_MONO, relief="flat", bd=0,
            state="disabled", wrap="word"
        )
        sb = ttk.Scrollbar(frame, orient="vertical",
                           command=self._txt_log.yview)
        self._txt_log.configure(yscrollcommand=sb.set)

        self._txt_log.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _aplica_estilos(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")

        # Configura as cores da treeview ativamente para o tema escuro
        estilo.configure(
            "Custom.Treeview",
            background=COR_LINHA_PAR, foreground=COR_TEXTO,
            fieldbackground=COR_LINHA_PAR,
            rowheight=26, borderwidth=0,
            font=FONTE_TABELA,
        )
        estilo.configure(
            "Custom.Treeview.Heading",
            background=COR_BORDA, foreground=COR_TEXTO,
            relief="flat", font=("Segoe UI", 9, "bold"),
        )
        
        # Corrige comportamento do Windows que sobrescreve cores das tags par/ímpar
        estilo.map(
            "Custom.Treeview",
            background=[("selected", COR_DESTAQUE)],
            foreground=[("selected", "white")],
        )
        
        estilo.configure(
            "TProgressbar",
            troughcolor=COR_PAINEL, background=COR_DESTAQUE,
            borderwidth=0, thickness=4
        )

    # ------------------------------------------------------------------
    # Recursos de Cópia e Menu de Contexto
    # ------------------------------------------------------------------
    def _cria_menu_contexto(self):
        self._menu = tk.Menu(self, tearoff=0, bg=COR_PAINEL, fg=COR_TEXTO, activebackground=COR_DESTAQUE)
        self._menu.add_command(label="Copiar Inscrição", command=lambda: self._copiar_celula_especifica(1))
        self._menu.add_command(label="Copiar Nº da CDA", command=lambda: self._copiar_celula_especifica(3))
        self._menu.add_separator()
        self._menu.add_command(label="Copiar Linha Completa", command=self._copiar_linha_completa)

    def _tenta_copiar_para_clipboard(self, texto: str):
        """Método encapsulado seguro para evitar travamentos de clipboard no Windows."""
        try:
            self.clipboard_clear()
            self.clipboard_append(texto)
            self.update() # Força a atualização no Windows
            return True
        except Exception as e:
            self._log_escrever(f"⚠️ Erro ao acessar a área de transferência: {e}\n")
            return False

    def _on_double_click(self, event):
        region = self._tree.identify_region(event.x, event.y)
        column = self._tree.identify_column(event.x)
        
        if not column:
            return
            
        col_idx = int(column.replace("#", "")) - 1

        if region == "heading":
            valores_coluna = []
            for child in self._tree.get_children(""):
                valores = self._tree.item(child, "values")
                if col_idx < len(valores):
                    val = valores[col_idx]
                    if val:
                        valores_coluna.append(str(val))
            
            if valores_coluna:
                texto = "\n".join(valores_coluna)
                if self._tenta_copiar_para_clipboard(texto):
                    self._log_escrever(f"📋 Coluna inteira copiada ({len(valores_coluna)} itens).\n")
            return

        item = self._tree.identify_row(event.y)
        if not item:
            return
            
        valores = self._tree.item(item, "values")
        if col_idx < len(valores):
            valor = valores[col_idx]
            if self._tenta_copiar_para_clipboard(valor):
                self._log_escrever(f"📋 Copiado para a área de transferência: {valor}\n")

    def _on_right_click(self, event):
        item = self._tree.identify_row(event.y)
        if item:
            self._tree.selection_set(item)
            self._menu.post(event.x_root, event.y_root)

    def _copiar_celula_especifica(self, col_idx):
        selecionado = self._tree.selection()
        if selecionado:
            valores = self._tree.item(selecionado[0], "values")
            if col_idx < len(valores):
                valor = valores[col_idx]
                if self._tenta_copiar_para_clipboard(valor):
                    self._log_escrever(f"📋 Copiado: {valor}\n")

    def _copiar_linha_completa(self):
        selecionado = self._tree.selection()
        if selecionado:
            valores = self._tree.item(selecionado[0], "values")
            linha_texto = "\t".join(str(v) for v in valores)
            if self._tenta_copiar_para_clipboard(linha_texto):
                self._log_escrever("📋 Linha completa copiada!\n")

    # ------------------------------------------------------------------
    # Interações
    # ------------------------------------------------------------------
    def _ao_fechar(self):
        """Intercepção segura para garantir encerramento total da aplicação e threads."""
        self._processando = False
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    def _centraliza(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw   = self.winfo_screenwidth()
        sh   = self.winfo_screenheight()
        x    = (sw - w) // 2
        y    = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

    def _selecionar_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar PDF de CDA",
            filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")]
        )
        if caminho:
            self._caminho_pdf.set(caminho)
            self._btn_processar.config(state="normal")
            self._log_escrever(f"Arquivo selecionado: {os.path.basename(caminho)}\n")

    def _iniciar_processamento(self):
        if self._processando:
            return
        caminho = self._caminho_pdf.get()
        if not caminho or caminho == "Nenhum arquivo selecionado":
            messagebox.showwarning("Atenção", "Selecione um arquivo PDF primeiro.")
            return

        self._limpar_resultados()
        self._processando = True
        self._btn_processar.config(state="disabled", text="⏳  Processando…")
        self._progresso.start(12)

        thread = threading.Thread(target=self._processar, args=(caminho,), daemon=True)
        thread.start()

    def _processar(self, caminho: str):
        try:
            registros, avisos = extrair_dados_pdf(caminho)
            if self._processando: # Evita tentar atualizar interface se janela estiver fechando
                self.after(0, lambda: self._exibir_resultados(registros, avisos, caminho))
        except Exception as exc:
            if self._processando:
                self.after(0, lambda: self._erro_processamento(str(exc)))

    def _exibir_resultados(self, registros: list[dict], avisos: list[str], caminho: str):
        self._progresso.stop()
        self._processando = False
        self._btn_processar.config(state="normal", text="▶  Processar")
        self._registros = registros

        # Habilita botões de ações adicionais
        self._btn_copiar_tudo.config(state="normal")
        self._btn_filtra_duplicados.config(state="normal")

        # Atualiza a tabela
        self._atualizar_tabela()

        total = len(registros)
        n_paginas = len(set(r["pagina"] for r in registros))
        n_avisos  = len(avisos)
        
        # A ordenação já é garantida pelo extrator

        # Estilização visual amigável do status de avisos
        if total > 0 and n_avisos > 0:
            # Se tem dados, avisos de páginas em branco são comuns e normais
            cor_av = COR_PAINEL
        else:
            cor_av = COR_ERRO if n_avisos else COR_SUCESSO
            
        self._lbl_avisos.config(text=f"Avisos: {n_avisos}", bg=cor_av)
        self._lbl_avisos.master.config(bg=cor_av)

        nome = os.path.basename(caminho)
        self._log_escrever(
            f"\n{'='*60}\n"
            f"Arquivo : {nome}\n"
            f"Registros extraídos : {total}\n"
            f"Páginas com dados   : {n_paginas}\n"
            f"{'='*60}\n"
        )
        
        if avisos:
            self._log_escrever("\n⚠️  Alertas de Importação:\n")
            for av in avisos:
                self._log_escrever(f"  • {av}\n")
        else:
            self._log_escrever("✔  Processamento finalizado com sucesso.\n")

        if total == 0:
            messagebox.showinfo(
                "Resultado",
                "Nenhum dado de CDA encontrado no PDF.\n"
                "Verifique a aba 'Log / Avisos' para mais detalhes."
            )

    def _erro_processamento(self, msg: str):
        self._progresso.stop()
        self._processando = False
        self._btn_processar.config(state="normal", text="▶  Processar")
        self._log_escrever(f"\n❌  Erro: {msg}\n")
        messagebox.showerror("Erro", f"Falha ao processar o PDF:\n\n{msg}")

    def _limpar(self):
        self._caminho_pdf.set("Nenhum arquivo selecionado")
        self._btn_processar.config(state="disabled")
        self._btn_copiar_tudo.config(state="disabled")
        self._btn_filtra_duplicados.config(state="disabled")
        self._filtrando_duplicados = False
        self._btn_filtra_duplicados.config(
            bg=COR_BORDA, fg=COR_TEXTO, text="🔍  Remover Duplicados",
            activebackground=COR_DESTAQUE, activeforeground="white"
        )
        self._limpar_resultados()
        self._lbl_total.config(text="Registros: —")
        self._lbl_paginas.config(text="Páginas: —")
        self._lbl_avisos.config(text="Avisos: —", bg=COR_AVISO)
        self._lbl_avisos.master.config(bg=COR_AVISO)

    def _limpar_resultados(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._registros = []
        self._txt_log.config(state="normal")
        self._txt_log.delete("1.0", "end")
        self._txt_log.config(state="disabled")

    def _atualizar_tabela(self):
        # 1. Limpa os itens visuais da treeview
        for item in self._tree.get_children():
            self._tree.delete(item)

        registros_a_exibir = []
        if self._filtrando_duplicados:
            # Aumenta a largura da coluna Pág. para 260 para exibir a lista completa sem cortes
            self._tree.column("pagina", width=260, minwidth=60, anchor="center")
            agrupados = {}
            for r in self._registros:
                chave = r["inscricao"].strip()
                if not chave:
                    continue
                if chave not in agrupados:
                    agrupados[chave] = {
                        "pagina": str(r["pagina"]),
                        "inscricao": chave,
                        "referencia": r["referencia"],
                        "cda": r["cda"],
                        "situacao": r["situacao"],
                        "paginas_lista": [r["pagina"]]
                    }
                else:
                    if r["pagina"] not in agrupados[chave]["paginas_lista"]:
                        agrupados[chave]["paginas_lista"].append(r["pagina"])
            
            for chave, reg in agrupados.items():
                reg["paginas_lista"].sort()
                reg["pagina"] = ", ".join(map(str, reg["paginas_lista"]))
                registros_a_exibir.append(reg)
        else:
            # Restaura a largura compacta original se não estiver filtrando
            self._tree.column("pagina", width=60, minwidth=40, anchor="center")
            registros_a_exibir = self._registros

        paginas_vistas = set()
        for idx, reg in enumerate(registros_a_exibir):
            tag = "par" if idx % 2 == 0 else "impar"
            if self._filtrando_duplicados:
                for p in reg["paginas_lista"]:
                    paginas_vistas.add(p)
            else:
                paginas_vistas.add(reg["pagina"])

            self._tree.insert("", "end", values=(
                reg["pagina"],
                reg["inscricao"],
                reg["referencia"],
                reg["cda"],
                reg["situacao"],
            ), tags=(tag,))

        total = len(registros_a_exibir)
        n_paginas = len(paginas_vistas)
        self._lbl_total.config(text=f"Registros: {total}")
        self._lbl_paginas.config(text=f"Páginas com dados: {n_paginas}")



    def _toggle_duplicados(self):
        self._filtrando_duplicados = not self._filtrando_duplicados
        if self._filtrando_duplicados:
            self._btn_filtra_duplicados.config(
                bg=COR_SUCESSO, fg="#1e2130", text="✓  Sem Duplicados",
                activebackground="#37b88f", activeforeground="#1e2130"
            )
            self._log_escrever("🔍 Filtro de duplicados ativado.\n")
        else:
            self._btn_filtra_duplicados.config(
                bg=COR_BORDA, fg=COR_TEXTO, text="🔍  Remover Duplicados",
                activebackground=COR_DESTAQUE, activeforeground="white"
            )
            self._log_escrever("🔍 Filtro de duplicados desativado.\n")
        self._atualizar_tabela()

    def _copiar_tudo(self):
        linhas = []
        # Adiciona cabeçalho amigável
        linhas.append("Pág.\tInscrição\tReferência\tNº da C.D.A\tSituação")
        for item in self._tree.get_children():
            valores = self._tree.item(item, "values")
            linhas.append("\t".join(str(v) for v in valores))
        
        if len(linhas) <= 1:
            messagebox.showinfo("Aviso", "Não há registros na tabela para copiar.")
            return

        texto_copiar = "\n".join(linhas)
        if self._tenta_copiar_para_clipboard(texto_copiar):
            self._log_escrever(f"📋 Copiados {len(linhas)-1} registros para a área de transferência.\n")
            messagebox.showinfo("Sucesso", f"{len(linhas)-1} registros copiados com sucesso!")

    def _log_escrever(self, texto: str):
        self._txt_log.config(state="normal")
        self._txt_log.insert("end", texto)
        self._txt_log.see("end")
        self._txt_log.config(state="disabled")




# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except Exception:
            pass

    app = FiscoCaptureApp()
    app.mainloop()


if __name__ == "__main__":
    main()
