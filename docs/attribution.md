# Attribution and licenses

ravel is an original implementation. The research inspection did not vendor or copy competitor implementation code. The project acknowledges the following work for mechanisms and comparison design. Their names do not imply affiliation or endorsement.

| Work | License / primary source | Use |
| --- | --- | --- |
| LEANN, LEANN Contributors | [MIT](https://github.com/StarTrail-org/LEANN/blob/a63f484a0b00627fbc641b500ee377d35344eb72/LICENSE), copyright 2025 LEANN Contributors | Inspiration: storage/computation tradeoffs; comparison target. |
| QMD, Tobi Lutke | [MIT](https://github.com/tobi/qmd/blob/86d2365d17fc682e491c2c53d1e4a884aee8682a/LICENSE), copyright 2024–2026 Tobi Lutke | Comparison target; established local hybrid retrieval and lexical-confidence shortcuts. |
| Codanna | [Apache-2.0](https://github.com/bartolli/codanna/blob/639917d868eda7dc789774c9c9d69b3753dd1b75/LICENSE), [NOTICE](https://github.com/bartolli/codanna/blob/639917d868eda7dc789774c9c9d69b3753dd1b75/NOTICE) | Comparison target; established structural code intelligence. |
| grepai, Yoan Bernabeu | [MIT](https://github.com/yoanbernabeu/grepai/blob/dd38459f31a8b25e49b886511a15667caf43478b/LICENSE), copyright 2026 Yoan Bernabeu | Comparison target; semantic/code-graph and incremental retrieval. |
| SQLite | [Public domain](https://sqlite.org/copyright.html) | Proven storage/full-text implementation via Python's sqlite3 module. |
| Python | [PSF license](https://docs.python.org/3/license.html) | Runtime and standard library. |

Third-party Python dependencies and downloaded model weights retain their own licenses. Installing an optional embedding or document parser extra does not transfer ownership of those components to ravel. Read the model card for the configured model, preserve license notices when redistributing weights, and account for its download separately from the index. See the package metadata for actual dependency bounds.

Benchmark sources are separate from the MIT-licensed ravel code:

- [ContextBench](https://arxiv.org/abs/2602.05892): Han Li and colleagues, 2026. [Dataset](https://huggingface.co/datasets/Contextbench/ContextBench), [evaluation code](https://github.com/EuniAI/ContextBench). Check dataset and upstream repository terms before redistribution.
- [Agent Retrieval Bench](https://arxiv.org/abs/2607.24882): Bowen Qin and Yi Xie, 2026. [Data licensing notes](https://github.com/eyuansu62/agent-retrieval-bench/blob/main/DATA_LICENSE.md) distinguish MIT evaluator/metadata from corpus files that retain each upstream repository's license.
- [CORE-Bench](https://arxiv.org/abs/2606.11864): Fuwei Zhang and colleagues, 2026. Its [dataset card](https://huggingface.co/datasets/zhangfw123/CORE-Bench) lists **CC-BY-NC-SA-4.0**. These data are not relicensed under ravel's MIT license.

Research comparisons use citations and independently written descriptions. If a future change vendors source, examples, corpus bytes or model weights, it must include the applicable full license and notices in the distribution. Downloading public source for a local benchmark does not authorize relicensing or silently bundling it in ravel packages.

Further prior art: [SelRoute](https://arxiv.org/abs/2604.02431), [Adaptive-RAG](https://arxiv.org/abs/2403.14403), [Matryoshka Representation Learning](https://arxiv.org/abs/2205.13147). See [research notes](research.md) for the scope of ravel's intended contribution and limitations.
