"""
pbix_analyzer.py
----------------
Extrai medidas DAX de um arquivo .pbix local, constrói o grafo de dependências
e gera um relatório JSON + Markdown pronto para análise com Claude.

Uso:
    python pbix_analyzer.py caminho/para/arquivo.pbix

Saída:
    <nome_arquivo>_measures.json   — grafo completo de medidas
    <nome_arquivo>_report.md       — relatório Markdown para colar no Claude

Dependência:
    pip install pbixray
"""

import sys
import re
import json
from pathlib import Path
from collections import defaultdict

try:
    from pbixray.core import PBIXRay
except ImportError:
    print("pbixray não encontrado. Instale com: pip install pbixray")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 1. Extração
# ---------------------------------------------------------------------------

def load_pbix(path: str) -> PBIXRay:
    return PBIXRay(path)


def extract_measures(model: PBIXRay) -> list[dict]:
    df = model.dax_measures
    if df is None or df.empty:
        return []

    measures = []
    for _, row in df.iterrows():
        measures.append({
            "name":        str(row.get("MeasureName", row.get("Name", ""))).strip(),
            "table":       str(row.get("TableName",   row.get("Table", ""))).strip(),
            "expression":  str(row.get("Expression",  "")).strip(),
            "description": str(row.get("Description", "")).strip(),
            "format":      str(row.get("FormatString", "")).strip(),
        })

    return measures


def extract_relationships(model: PBIXRay) -> list[dict]:
    df = model.relationships
    if df is None or df.empty:
        return []

    rels = []
    for _, row in df.iterrows():
        rels.append({col: str(val).strip() for col, val in row.items()})
    return rels


# ---------------------------------------------------------------------------
# 2. Grafo de dependências
# ---------------------------------------------------------------------------

def build_dependency_graph(measures: list[dict]) -> dict[str, list[str]]:
    """
    Para cada medida, encontra quais outras medidas ela referencia.
    Detecta padrões: [MeasureName], [Table].[MeasureName] ou MEASURE(...)
    """
    measure_names = {m["name"] for m in measures}
    # Regex captura qualquer [Palavra] dentro da expressão
    ref_pattern = re.compile(r'\[([^\]]+)\]')

    graph: dict[str, list[str]] = {}

    for m in measures:
        expr = m["expression"]
        candidates = ref_pattern.findall(expr)
        deps = sorted({c for c in candidates if c in measure_names and c != m["name"]})
        graph[m["name"]] = deps

    return graph


def build_reverse_graph(graph: dict[str, list[str]]) -> dict[str, list[str]]:
    """Quais medidas dependem DE cada medida (impacto)."""
    reverse: dict[str, list[str]] = defaultdict(list)
    for measure, deps in graph.items():
        for dep in deps:
            reverse[dep].append(measure)
    return dict(reverse)


def classify_measures(
    measures: list[dict],
    graph: dict[str, list[str]],
    reverse: dict[str, list[str]],
) -> dict[str, str]:
    """
    base       — sem dependências de outras medidas
    derived    — depende de outras medidas
    top_level  — nenhuma outra medida depende dela (folha do grafo)
    """
    classification = {}
    for m in measures:
        name = m["name"]
        has_deps    = bool(graph.get(name))
        has_impact  = bool(reverse.get(name))

        if not has_deps and has_impact:
            classification[name] = "base"
        elif has_deps and not has_impact:
            classification[name] = "top_level"
        elif has_deps and has_impact:
            classification[name] = "derived"
        else:
            classification[name] = "standalone"

    return classification


def compute_depth(
    name: str,
    graph: dict[str, list[str]],
    cache: dict[str, int],
) -> int:
    if name in cache:
        return cache[name]
    deps = graph.get(name, [])
    if not deps:
        cache[name] = 0
        return 0
    depth = 1 + max(compute_depth(d, graph, cache) for d in deps)
    cache[name] = depth
    return depth


# ---------------------------------------------------------------------------
# 3. Montagem do payload
# ---------------------------------------------------------------------------

def build_payload(path: str) -> dict:
    model     = load_pbix(path)
    measures  = extract_measures(model)
    rels      = extract_relationships(model)
    graph     = build_dependency_graph(measures)
    reverse   = build_reverse_graph(graph)
    classes   = classify_measures(measures, graph, reverse)

    depth_cache: dict[str, int] = {}

    enriched = []
    for m in measures:
        name = m["name"]
        enriched.append({
            **m,
            "dependencies":      graph.get(name, []),
            "used_by":           reverse.get(name, []),
            "classification":    classes.get(name, "unknown"),
            "dependency_depth":  compute_depth(name, graph, depth_cache),
        })

    # Ordena por profundidade decrescente (mais complexas primeiro)
    enriched.sort(key=lambda x: x["dependency_depth"], reverse=True)

    return {
        "file":          Path(path).name,
        "total_measures": len(enriched),
        "measures":      enriched,
        "relationships": rels,
    }


# ---------------------------------------------------------------------------
# 4. Relatório Markdown
# ---------------------------------------------------------------------------

def build_markdown(payload: dict) -> str:
    lines = []
    lines.append(f"# Análise de Medidas DAX — {payload['file']}")
    lines.append(f"\n**Total de medidas:** {payload['total_measures']}\n")

    # Resumo por classificação
    from collections import Counter
    counts = Counter(m["classification"] for m in payload["measures"])
    lines.append("## Classificação")
    lines.append(f"- 🟢 **Base** (sem dependências): {counts.get('base', 0)}")
    lines.append(f"- 🔵 **Derivada** (depende de outras e é usada): {counts.get('derived', 0)}")
    lines.append(f"- 🔴 **Top-level** (resultado final, não reutilizada): {counts.get('top_level', 0)}")
    lines.append(f"- ⚪ **Standalone** (isolada): {counts.get('standalone', 0)}")

    # Medidas mais complexas (top 10 por profundidade)
    lines.append("\n## Medidas mais complexas (por profundidade de dependência)")
    top = sorted(payload["measures"], key=lambda x: x["dependency_depth"], reverse=True)[:10]
    for m in top:
        lines.append(f"- **{m['name']}** (profundidade {m['dependency_depth']}, tabela: {m['table']})")

    # Detalhes de cada medida
    lines.append("\n## Detalhes das Medidas\n")
    for m in payload["measures"]:
        icon = {"base": "🟢", "derived": "🔵", "top_level": "🔴", "standalone": "⚪"}.get(m["classification"], "❓")
        lines.append(f"### {icon} {m['name']} ({m['table']})")
        if m["description"]:
            lines.append(f"> {m['description']}")
        lines.append(f"**Classificação:** {m['classification']} | **Profundidade:** {m['dependency_depth']}")
        if m["dependencies"]:
            lines.append(f"**Depende de:** {', '.join(m['dependencies'])}")
        if m["used_by"]:
            lines.append(f"**Usada por:** {', '.join(m['used_by'])}")
        lines.append(f"\n```dax\n{m['expression']}\n```\n")

    # Relacionamentos
    if payload["relationships"]:
        lines.append("## Relacionamentos")
        for r in payload["relationships"]:
            lines.append(f"- {r}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Uso: python pbix_analyzer.py <arquivo.pbix>")
        sys.exit(1)

    pbix_path = sys.argv[1]
    if not Path(pbix_path).exists():
        print(f"Arquivo não encontrado: {pbix_path}")
        sys.exit(1)

    print(f"Lendo {pbix_path}...")
    payload = build_payload(pbix_path)

    stem = Path(pbix_path).stem
    json_out = Path(pbix_path).parent / f"{stem}_measures.json"
    md_out   = Path(pbix_path).parent / f"{stem}_report.md"

    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(md_out, "w", encoding="utf-8") as f:
        f.write(build_markdown(payload))

    print(f"✅ JSON:     {json_out}")
    print(f"✅ Markdown: {md_out}")
    print(f"\nResumo: {payload['total_measures']} medidas extraídas.")

    # Mostra as 5 mais complexas no terminal
    top5 = sorted(payload["measures"], key=lambda x: x["dependency_depth"], reverse=True)[:5]
    print("\nTop 5 medidas mais complexas:")
    for m in top5:
        print(f"  [{m['dependency_depth']}] {m['name']} ({m['table']})")


if __name__ == "__main__":
    main()