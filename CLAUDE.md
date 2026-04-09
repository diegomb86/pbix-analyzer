# PBIX Analyzer — CLAUDE.md

Ferramenta de análise e visualização de medidas DAX extraídas de arquivos `.pbix` do Power BI.
Desenvolvida para uso local por analistas/engenheiros de BI que precisam auditar, debugar e documentar modelos complexos.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Extração do modelo | `pbixray` |
| Backend / API | `FastAPI` + `uvicorn` |
| Interface web | HTML + JS vanilla (single file, sem build step) |
| Grafo visual | `vis-network` (CDN) |
| Análise DAX | parsing regex + grafo de dependências em Python puro |

> Sem frameworks frontend complexos. A UI é um único `index.html` servido pelo FastAPI.
> O objetivo é zero fricção: rodar com um comando, abrir no browser, funcionar.

---

## Estrutura do projeto

```
pbix-analyzer/
├── CLAUDE.md               ← este arquivo
├── main.py                 ← FastAPI app (servidor + API)
├── analyzer.py             ← lógica de extração e grafo (pbixray)
├── static/
│   └── index.html          ← interface completa (HTML + JS + CSS inline)
├── requirements.txt
└── uploads/                ← pasta temporária para .pbix enviados (gitignored)
```

---

## Funcionalidades esperadas

### Já implementado (`pbix_analyzer.py` legado)
- [x] Extração de medidas via `pbixray`
- [x] Grafo de dependências bidirecional
- [x] Classificação: base / derived / top_level / standalone
- [x] Cálculo de profundidade de dependência
- [x] Exportação JSON + Markdown

### A implementar (objetivo desta evolução)
- [ ] Interface web local servida via FastAPI
- [ ] Upload de `.pbix` via browser (drag & drop ou file picker)
- [ ] Visualização do grafo com `vis-network`
  - Nós coloridos por classificação (base=verde, derived=azul, top_level=vermelho, standalone=cinza)
  - Tamanho do nó proporcional à profundidade
  - Clique no nó abre painel lateral com expressão DAX completa
  - Highlight de dependências ao hover
- [ ] Painel lateral com detalhes da medida selecionada
- [ ] Busca/filtro de medidas por nome ou tabela
- [ ] Exportação do relatório Markdown via botão

---

## Comandos de desenvolvimento

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar o servidor (abre automaticamente no browser)
python main.py

# O servidor sobe em http://localhost:8000
# A UI é acessada diretamente no browser após o comando acima
```

---

## API REST (FastAPI)

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/upload` | Recebe o `.pbix`, extrai o modelo, retorna JSON com medidas e grafo |
| `GET` | `/` | Serve o `index.html` |
| `GET` | `/health` | Healthcheck simples |

### Contrato do `/upload` response

```json
{
  "file": "relatorio.pbix",
  "total_measures": 47,
  "measures": [
    {
      "name": "Receita Líquida × Margem",
      "table": "Measures",
      "expression": "[Receita Líquida] * [Margem Bruta]",
      "description": "",
      "format": "0.00%",
      "dependencies": ["Receita Líquida", "Margem Bruta"],
      "used_by": [],
      "classification": "top_level",
      "dependency_depth": 3
    }
  ],
  "relationships": [
    {
      "FromTable": "fVendas",
      "FromColumn": "id_produto",
      "ToTable": "dProduto",
      "ToColumn": "id_produto",
      "CrossFilteringBehavior": "OneDirection"
    }
  ]
}
```

---

## Convenções de código

- **Python**: type hints em todas as funções públicas; docstrings curtas e objetivas
- **Sem ORM**: dados manipulados como `list[dict]` ou `pd.DataFrame` direto
- **Sem autenticação**: ferramenta local, sem multi-tenant
- **Uploads temporários**: salvar em `uploads/` com nome único (uuid), deletar após extração
- **Erros**: FastAPI deve retornar JSON `{"error": "mensagem legível"}` com status adequado (400, 422, 500)
- **CORS**: habilitado para `localhost` (facilita testes com extensões de browser)

---

## Comportamento da UI

### Fluxo principal
1. Usuário arrasta ou seleciona `.pbix`
2. Upload dispara `POST /upload`
3. Loader aparece enquanto processa
4. Grafo renderiza com `vis-network`
5. Clique num nó → painel lateral abre com detalhes

### Cores dos nós (vis-network)
| Classificação | Cor |
|---|---|
| `base` | `#22c55e` (verde) |
| `derived` | `#3b82f6` (azul) |
| `top_level` | `#ef4444` (vermelho) |
| `standalone` | `#94a3b8` (cinza) |

### Legenda sempre visível no canto superior direito da área do grafo

### Painel lateral (ao clicar num nó)
- Nome da medida + tabela
- Badge de classificação
- Profundidade
- Depende de: (lista clicável — clicar navega para aquela medida no grafo)
- Usada por: (idem)
- Expressão DAX em bloco de código com syntax highlight leve

---

## Contexto de domínio (importante para sugestões de análise)

- Arquivos `.pbix` são do **Power BI Desktop**
- Medidas DAX frequentemente encadeadas em 3-5 níveis de profundidade
- Tabelas comuns no contexto: `fVendas`, `dProduto`, `dFornecedor`, `dCalendario`, `Measures` (tabela virtual de medidas)
- KPIs típicos de exemplo: `Receita Líquida`, `Margem Bruta`, `Custo Total`, `Estoque`, `Receita Líquida × Margem`
- Foco de manutenção: identificar onde uma medida quebra dado um filtro específico (ex: filtro por fornecedor ou período)

---

## O que NÃO fazer

- Não usar `streamlit` ou `dash` — a UI deve ser HTML puro servido pelo FastAPI
- Não criar autenticação ou sessões
- Não persistir dados entre sessões (cada upload é stateless)
- Não tentar parsear DAX como AST completo — regex de `[referências]` é suficiente para o grafo de dependências
- Não usar banco de dados — tudo em memória durante a requisição