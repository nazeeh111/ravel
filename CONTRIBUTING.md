# Contributing

Small, reproducible improvements are welcome. Open an issue with the corpus size,
command, Python/platform versions and a minimal public reproduction. Do not attach
private indexes, source trees, credentials or query history.

```sh
python -m pip install -e '.[dev,documents]'
python -m pytest -q
ruff check src tests
python -m build
```

The offline test suite uses deterministic fake vectors solely to test mechanics;
quality/performance benchmarks use real local models and disclose their versions.
See [benchmark methodology](docs/benchmarks.md) and [external comparisons](docs/comparison.md).
Preserve source provenance, freshness defaults, permission boundaries, zero paid
API requirements and dependency attribution. Discuss large dependencies or new
personal-data connectors before implementation.
