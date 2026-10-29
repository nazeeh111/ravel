"""Render benchmark charts from retained measurements, never hand-entered claims.

uv run --with matplotlib --python .venv/bin/python scripts/plot_benchmarks.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'benchmarks' / 'results' / 'summary.json'
plt.rcParams.update({'font.family': ['DejaVu Sans', 'Arial', 'sans-serif'], 'font.size': 12, 'svg.fonttype': 'none',
                     'figure.facecolor': '#f5f4ef', 'axes.facecolor': '#f5f4ef',
                     'text.color': '#202c2a', 'axes.labelcolor': '#697570',
                     'xtick.color': '#697570', 'ytick.color': '#202c2a'})


def clean(ax):
    ax.spines[['top', 'right', 'left', 'bottom']].set_visible(False)
    ax.tick_params(axis='both', length=0)
    ax.grid(axis='x', alpha=0.2, color='#697570')
    ax.set_axisbelow(True)


def main():
    data = json.loads(DATA.read_text())
    assert data['all_workers_same_source'], 'Refuse to chart mixed source versions'
    lookup = {r['name']: r for r in data['summary']}
    order = ['lexical_full', 'hybrid_full', 'semantic_full', 'heuristic_full',
             'learned_full', 'heuristic_small', 'heuristic_nocache']
    labels = ['Lexical', 'Fixed hybrid', 'Semantic', 'Auto heuristic', 'Learned selector',
              'Auto / 1.5 KiB cache', 'Auto / no cache']
    rows = [lookup[key] for key in order]
    colors = ['#9aa49e', '#739c91', '#21695c', '#aa6040', '#c39279', '#a1b4aa', '#bdc7bf']
    fig, axes = plt.subplots(1, 3, figsize=(12, 6.3), gridspec_kw={'width_ratios': [1.25, 1, 1]})
    fields = [('mrr', 'Ranking quality', 'MRR, higher is better'),
              ('mean_context_byte_upper_bound', 'Evidence payload', 'UTF-8 bytes, not exact tokens'),
              ('warm_p50_ms', 'Warm query p50', 'Milliseconds, freshness included')]
    for i, (ax, (field, title, xlabel)) in enumerate(zip(axes, fields)):
        vals = [row[field] for row in rows]
        ax.barh(range(len(rows)), vals, color=colors, height=0.56)
        ax.invert_yaxis()
        ax.set_yticks(range(len(rows)), labels if i == 0 else [''] * len(rows))
        ax.set_title(title, loc='left', fontsize=12, fontweight='bold', pad=18)
        ax.set_xlabel(xlabel, fontsize=11, labelpad=12)
        ax.set_xlim(0, (1.1 if field == 'mrr' else max(vals) * 1.25))
        for j, val in enumerate(vals):
            text = f'{val:.3f}' if field == 'mrr' else f'{val:,.0f}'
            ax.text(val + ax.get_xlim()[1]*.02, j, text, va='center', fontsize=11)
        clean(ax)
    fig.suptitle('ravel  /  measured choices, visible costs', x=.03, y=.97, ha='left', fontsize=19, fontweight='bold')
    fig.text(.03, .89, '24 held-out queries · BGE-small · 3 repeats · tiny authored code/document corpus', color='#697570', fontsize=12)
    fig.text(.03, .045, 'Local observations under concurrent host load. Models preloaded for semantic rows. Full source verification included.', fontsize=11, color='#697570')
    fig.text(.03, .012, 'Source: benchmarks/results/summary.json · See docs/benchmarks.md for protocol, failures, cold start and limits.', fontsize=11, color='#697570')
    fig.subplots_adjust(left=.20, right=.97, top=.80, bottom=.18, wspace=.22)
    fig.savefig(ROOT / 'docs/assets/benchmarks.svg')
    plt.close(fig)

    external = json.loads((ROOT / 'benchmarks/external/summary.json').read_text())
    byname = {r['run']: r for r in external}
    keys = ['leann.json','faiss.json','ravel-lexical-cli.json','codanna-semantic.json',
            'ravel-matched-auto.json','grepai-semantic.json','qmd-bm25.json','qmd-vector.json']
    names = ['LEANN compact','Exact FAISS + metadata','ravel lexical','Codanna semantic',
             'ravel auto / matched MiniLM','grepai semantic','QMD BM25','QMD structured vector']
    vals = [byname[k]['index_bytes'] / 1024 for k in keys]
    fig, ax = plt.subplots(figsize=(12.8, 5.8))
    ax.barh(range(8), vals, height=.56, color=['#21695c' if 'ravel' not in k else '#aa6040' for k in keys])
    ax.set_yticks(range(8), names)
    ax.invert_yaxis()
    ax.set_xscale('log')
    ax.set_xlim(10, max(vals)*2.2)
    for j, val in enumerate(vals):
        ax.text(val*1.07, j, f'{val:,.1f} KiB', va='center', fontsize=12)
    clean(ax)
    ax.set_xlabel('Complete index storage · KiB · logarithmic axis · models/runtime excluded', labelpad=15)
    fig.suptitle('Small corpus, real fixed costs', x=.03, y=.97, ha='left', fontsize=20, fontweight='bold')
    fig.text(.03,.895,'32 files / 5,869 bytes · competitors can be smaller · capabilities and chunking differ',fontsize=11,color='#697570')
    fig.text(.03,.045,'Measured local configurations, not storage ratios at scale. See docs/comparison.md and raw adapters.',fontsize=12,color='#697570')
    fig.subplots_adjust(left=.29,right=.95,top=.81,bottom=.18)
    fig.savefig(ROOT/'docs/assets/comparison.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
