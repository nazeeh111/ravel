# Attribution and licenses

Runtime dependencies and benchmark materials retain their own licenses. No competitor implementation is vendored. Comparison sources and design context are documented in [research notes](research.md).

| Work | License / primary source | Use |
| --- | --- | --- |
| SQLite | [Public domain](https://sqlite.org/copyright.html) | Proven storage/full-text implementation via Python's sqlite3 module. |
| Python | [PSF license](https://docs.python.org/3/license.html) | Runtime and standard library. |

Third-party Python dependencies and downloaded model weights retain their own licenses. Installing an optional embedding or document parser extra does not transfer ownership of those components to ravel. Read the model card for the configured model, preserve license notices when redistributing weights, and account for its download separately from the index. See the package metadata for actual dependency bounds.

Benchmark sources are separate from the MIT-licensed ravel code:

- [ContextBench](https://arxiv.org/abs/2602.05892): Han Li and colleagues, 2026. [Dataset](https://huggingface.co/datasets/Contextbench/ContextBench), [evaluation code](https://github.com/EuniAI/ContextBench). Check dataset and upstream repository terms before redistribution.
- [Agent Retrieval Bench](https://arxiv.org/abs/2607.24882): Bowen Qin and Yi Xie, 2026. [Data licensing notes](https://github.com/eyuansu62/agent-retrieval-bench/blob/main/DATA_LICENSE.md) distinguish MIT evaluator/metadata from corpus files that retain each upstream repository's license.
- [CORE-Bench](https://arxiv.org/abs/2606.11864): Fuwei Zhang and colleagues, 2026. Its [dataset card](https://huggingface.co/datasets/zhangfw123/CORE-Bench) lists **CC-BY-NC-SA-4.0**. These data are not relicensed under ravel's MIT license.

Research comparisons use citations and independently written descriptions. If a future change vendors source, examples, corpus bytes or model weights, it must include the applicable full license and notices in the distribution. Downloading public source for a local benchmark does not authorize relicensing or silently bundling it in ravel packages.
