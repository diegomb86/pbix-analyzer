# PBIX Analyzer

Ferramenta local para análise e visualização de medidas DAX extraídas de arquivos `.pbix` do Power BI.
Gera um grafo interativo de dependências entre medidas e permite inspecionar expressões DAX diretamente no browser.

---

## Pré-requisitos

- Python 3.12
- pip

---

## Instalação

```bash
# Clone ou baixe o projeto
cd pbix-analyzer

# Instale as dependências
pip install -r requirements.txt
```

---

## Como executar

```bash
python main.py
```

O servidor sobe em `http://localhost:8000` e o browser abre automaticamente.

Para parar o servidor, pressione `Ctrl+C` no terminal.

---

## Como abrir um arquivo .pbix

Há duas formas de carregar um arquivo na interface:

**1. Drag & drop**
Arraste o arquivo `.pbix` diretamente para a área central da página.

**2. File picker**
Clique no botão **"Abrir .pbix"** no canto superior direito e selecione o arquivo.

Após o upload, o servidor extrai todas as medidas DAX, calcula o grafo de dependências e renderiza o resultado na tela.

---

## Como usar a interface

### Grafo de dependências

Cada nó representa uma medida DAX. As arestas indicam dependências: uma aresta de A → B significa que B utiliza A em sua expressão.

**Cores dos nós:**

| Cor | Classificação | Significado |
|---|---|---|
| Verde | Base | Sem dependências de outras medidas |
| Azul | Derivada | Depende de outras medidas e é reutilizada |
| Vermelho | Top-level | Resultado final, não reutilizada por nenhuma outra |
| Cinza | Standalone | Isolada, sem dependências e sem uso |

**Tamanho do nó:** proporcional à profundidade de dependência — nós maiores têm cadeias de dependência mais longas.

**Interações:**
- **Hover** sobre um nó — destaca o nó e seus vizinhos diretos
- **Clique** em um nó — abre o painel lateral com detalhes da medida
- **Scroll** — zoom in/out no grafo
- **Arrastar** — mover e reorganizar o grafo

### Painel lateral

Ao clicar em uma medida, o painel lateral exibe:

- Nome e tabela de origem
- Badge de classificação e profundidade de dependência
- **Depende de:** lista de medidas que esta medida referencia (clicável — navega para a medida)
- **Usada por:** lista de medidas que referenciam esta medida (clicável)
- Expressão DAX completa em bloco de código

### Busca e filtro

Use o campo de busca na barra superior para filtrar medidas por **nome** ou **tabela**.
As medidas que não correspondem ao filtro ficam esmaecidas no grafo.
Se houver exatamente uma correspondência, o grafo centraliza automaticamente naquela medida.

### Exportar Markdown

Clique em **"Exportar Markdown"** para baixar um relatório `.md` com:
- Contagem por classificação
- Top 10 medidas mais complexas por profundidade
- Detalhes completos de cada medida (expressão DAX, dependências, classificação)

> O botão solicita o arquivo `.pbix` novamente antes de gerar o relatório, pois o servidor não armazena arquivos entre requisições.

---

## Visualizar o JSON da API

O endpoint `/upload` retorna um JSON estruturado com todas as medidas e relacionamentos.
Para inspecioná-lo diretamente:

**Via curl:**
```bash
curl -s -X POST http://localhost:8000/upload \
  -F "file=@caminho/para/arquivo.pbix" | python -m json.tool
```

**Via Python:**
```python
import requests

with open("arquivo.pbix", "rb") as f:
    res = requests.post("http://localhost:8000/upload", files={"file": f})

data = res.json()
print(f"Total de medidas: {data['total_measures']}")

for m in data["measures"]:
    print(m["name"], "|", m["classification"], "| profundidade:", m["dependency_depth"])
```

**Estrutura do JSON retornado:**
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

## Uso via linha de comando (modo legado)

O `analyzer.py` também pode ser executado diretamente para gerar arquivos JSON e Markdown localmente, sem o servidor:

```bash
python analyzer.py caminho/para/arquivo.pbix
```

Gera dois arquivos na mesma pasta do `.pbix`:
- `<nome>_measures.json` — grafo completo de medidas
- `<nome>_report.md` — relatório Markdown
