"""SQLite-backed source evidence with explicit adaptive retrieval costs."""
from __future__ import annotations

import json
import heapq
import hashlib
import os
import re
import sqlite3
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from . import planner
from .embeddings import LocalEmbedder, MODEL, cosine
from .sources import chunks, discover, read_source, tokenize

SCHEMA = """
CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, digest TEXT NOT NULL, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks(
 id INTEGER PRIMARY KEY, path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
 start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, text TEXT NOT NULL,
 symbol TEXT NOT NULL, calls TEXT NOT NULL, search_text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(path, symbol, search_text, content='chunks', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS chunks_insert AFTER INSERT ON chunks BEGIN
 INSERT INTO fts(rowid,path,symbol,search_text) VALUES(new.id,new.path,new.symbol,new.search_text); END;
CREATE TRIGGER IF NOT EXISTS chunks_delete AFTER DELETE ON chunks BEGIN
 INSERT INTO fts(fts,rowid,path,symbol,search_text) VALUES('delete',old.id,old.path,old.symbol,old.search_text); END;
CREATE TABLE IF NOT EXISTS vectors(
 chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
 vector BLOB NOT NULL, hits INTEGER NOT NULL DEFAULT 1, cost_ms REAL NOT NULL, used REAL NOT NULL);
"""


def token_cost(text):
    """Conservative UTF-8 byte budget, safe upper bound for byte-fallback tokenizers.

    Byte count deliberately overestimates usual English tokens. No tokenizer/model
    download. Counts the entire serialized evidence result including provenance.
    """
    return len(text.encode("utf-8"))


class Index:
    def __init__(self, root=".", *, db_path=None, cache_bytes=None, embedder=None):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("root must be a directory")
        self.path = Path(db_path) if db_path else self.root / ".ravel" / "index.sqlite3"
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError("index directory and database must not be symlinks")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        os.chmod(self.path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.executescript(SCHEMA)
        old = self._get("root")
        if old is not None and old != str(self.root):
            self.db.close()
            raise ValueError("index belongs to a different source root")
        self._set("root", str(self.root))
        self.db.commit()
        if cache_bytes is None:
            cache_bytes = int(self._get("cache_budget") or 8 * 1024 * 1024)
        if not isinstance(cache_bytes, int) or isinstance(cache_bytes, bool) or cache_bytes < 0:
            self.db.close()
            raise ValueError("cache_bytes must be a nonnegative integer")
        self.cache_budget = cache_bytes
        self._set("cache_budget", cache_bytes)
        self._trim_cache()
        self.db.commit()
        self._embedder = embedder
        self._embed_ms = float(self._get("embed_ms") or 12)

    def _get(self, key):
        row = self.db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _set(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (key, str(value)))

    @property
    def semantic(self):
        return self._embedder is not None or self._get("model") is not None

    def _model(self):
        if self._embedder is None:
            self._embedder = LocalEmbedder(self.path.parent / "models")
        return self._embedder

    def enable_semantic(self, *, download=False):
        self._embedder = LocalEmbedder(self.path.parent / "models", download=download)
        self._set("model", MODEL)
        self.db.commit()

    def revision(self):
        try:
            proc = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, timeout=3)
            return proc.stdout.strip() if proc.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    @contextmanager
    def _transaction(self):
        if self.db.in_transaction:
            yield
        else:
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                yield

    def sync(self):
        """Hash eligible source bytes each call. Delete all no-longer-readable entries.

        Entire scan and mutations are one transaction. Reading a denied file is
        never retried via another path. Vectors cascade on edit/delete/rename.
        """
        start = time.perf_counter()
        seen, changed, skipped = set(), 0, 0
        with self._transaction():
            force = self._get("parser_version") != "2"
            old = {r["path"]: r["digest"] for r in self.db.execute("SELECT path,digest FROM files")}
            for path in discover(self.root):
                source = read_source(self.root, path)
                if source is None:
                    skipped += 1
                    continue
                seen.add(source.path)
                if old.get(source.path) == source.digest and not force:
                    continue
                self.db.execute("DELETE FROM files WHERE path=?", (source.path,))
                self.db.execute("INSERT INTO files VALUES (?,?,?)", (source.path, source.digest, source.kind))
                for c in chunks(source.text, path.suffix.lower()):
                    self.db.execute("INSERT INTO chunks(path,start_line,end_line,text,symbol,calls,search_text) "
                                    "VALUES (?,?,?,?,?,?,?)", (source.path, c.start, c.end, c.text, c.symbol,
                                                              json.dumps(c.calls), " ".join(tokenize(c.text))))
                changed += 1
            removed = old.keys() - seen
            self.db.executemany("DELETE FROM files WHERE path=?", [(p,) for p in removed])
            self._set("revision", self.revision() or "")
            self._set("parser_version", "2")
        return {"changed": changed, "removed": len(removed), "skipped": skipped,
                "files": len(seen), "elapsed_ms": round((time.perf_counter() - start) * 1000, 3)}

    def _lexical(self, query, depth):
        phrase = len(query) >= 2 and query.startswith('"') and query.endswith('"')
        terms = (tokenize(query) if phrase else list(dict.fromkeys(tokenize(query))))[:32]
        if not terms:
            return []
        expression = '"' + " ".join(terms) + '"' if phrase else " OR ".join('"' + t + '"' for t in terms)
        rows = self.db.execute("SELECT chunks.*,bm25(fts,8,12,1) AS rank FROM fts JOIN chunks "
                               "ON chunks.id=fts.rowid WHERE fts MATCH ? ORDER BY rank LIMIT ?",
                               (expression, depth)).fetchall()
        stripped = query.strip('"').lower()
        def bonus(row):
            symbol = row["symbol"].lower()
            return (3 if stripped == symbol or stripped == symbol.rsplit(".", 1)[-1] else 0) + (
                2 if stripped == row["path"].lower() or stripped == Path(row["path"]).name.lower() else 0)
        rows = sorted(rows, key=lambda r: (-bonus(r), r["rank"], r["id"]))
        return rows

    def _coverage(self, query, row):
        q = set(tokenize(query))
        body = set(tokenize(row["text"] + " " + row["path"] + " " + row["symbol"]))
        return len(q & body) / max(1, len(q))

    def _trim_cache(self):
        # Utility per byte: observed hit frequency * measured regeneration cost.
        total = self.db.execute("SELECT COALESCE(sum(length(vector)),0) FROM vectors").fetchone()[0]
        if total <= self.cache_budget:
            return 0
        evicted = 0
        for row in self.db.execute("SELECT chunk_id,length(vector) AS size FROM vectors "
                                   "ORDER BY (hits * max(cost_ms,0.01)) / length(vector), used").fetchall():
            self.db.execute("DELETE FROM vectors WHERE chunk_id=?", (row["chunk_id"],))
            total -= row["size"]
            evicted += 1
            if total <= self.cache_budget:
                break
        return evicted

    def _dense(self, query, candidates, deadline):
        start = time.perf_counter()
        model = self._model()  # Model cold-start can exceed a soft latency target.
        q = model.embed([query], query=True)[0]
        scores, hits, misses = {}, 0, 0
        for row in candidates:
            if time.perf_counter() > deadline and scores:
                break
            cached = self.db.execute("SELECT vector FROM vectors WHERE chunk_id=?", (row["id"],)).fetchone()
            if cached:
                v = cached[0]
                hits += 1
                self.db.execute("UPDATE vectors SET hits=hits+1,used=? WHERE chunk_id=?", (time.time(), row["id"]))
            else:
                before = time.perf_counter()
                v = model.embed([row["symbol"] + "\n" + row["text"]])[0]
                cost = (time.perf_counter() - before) * 1000
                self._embed_ms = 0.8 * self._embed_ms + 0.2 * cost
                self.db.execute("INSERT OR REPLACE INTO vectors VALUES (?,?,1,?,?)",
                                (row["id"], v, cost, time.time()))
                misses += 1
            scores[row["id"]] = cosine(q, v)
        self._set("embed_ms", self._embed_ms)
        evicted = self._trim_cache()
        return scores, {"cache_hits": hits, "cache_misses": misses, "cache_evictions": evicted,
                        "dense_ms": round((time.perf_counter() - start) * 1000, 3)}

    def _semantic_scan(self, query, depth, latency_ms):
        """Stream every cached vector, then sample bounded uncached work.

        Cached vectors never compete for a prefix of the candidate allocation.
        A query-seeded strided sample spreads cold work across source order.
        Partial coverage is explicit in metrics; exact full search is available
        after materialization when the latency target permits a complete scan.
        """
        model = self._model()
        q = model.embed([query], query=True)[0]
        deadline = time.perf_counter() + latency_ms / 1000
        best, hits, misses, scanned = [], 0, 0, 0
        def keep(id_, value):
            if len(best) < depth:
                heapq.heappush(best, (value, id_))
            elif value > best[0][0]:
                heapq.heapreplace(best, (value, id_))
        for row in self.db.execute("SELECT chunk_id,vector FROM vectors ORDER BY chunk_id"):
            if time.perf_counter() > deadline and scanned:
                break
            keep(row["chunk_id"], cosine(q, row["vector"]))
            hits += 1
            scanned += 1
        missing = self.db.execute("SELECT count(*) FROM chunks WHERE id NOT IN (SELECT chunk_id FROM vectors)").fetchone()[0]
        # Rank-stratified offsets, deterministic for each query and corpus.
        seed = int.from_bytes(hashlib.sha256(query.encode()).digest()[:8], "little")
        offsets = sorted({(seed % max(1, missing) + int(i * missing / max(1, depth))) % max(1, missing)
                          for i in range(min(depth, missing))})
        for offset in offsets:
            if time.perf_counter() > deadline and scanned:
                break
            row = self.db.execute("SELECT * FROM chunks WHERE id NOT IN (SELECT chunk_id FROM vectors) "
                                  "ORDER BY id LIMIT 1 OFFSET ?", (offset - misses,)).fetchone()
            if row is None:
                continue
            before = time.perf_counter()
            v = model.embed([row["symbol"] + "\n" + row["text"]])[0]
            cost = (time.perf_counter() - before) * 1000
            self._embed_ms = 0.8 * self._embed_ms + 0.2 * cost
            self.db.execute("INSERT INTO vectors VALUES (?,?,1,?,?)", (row["id"], v, cost, time.time()))
            keep(row["id"], cosine(q, v))
            scanned += 1
            misses += 1
        for _, id_ in best:
            self.db.execute("UPDATE vectors SET hits=hits+1,used=? WHERE chunk_id=?", (time.time(), id_))
        self._set("embed_ms", self._embed_ms)
        evicted = self._trim_cache()
        scores = {id_: value for value, id_ in best}
        pool = {}
        for id_ in scores:
            pool[id_] = self.db.execute("SELECT * FROM chunks WHERE id=?", (id_,)).fetchone()
        return scores, pool, {"cache_hits": hits, "cache_misses": misses,
                              "cache_evictions": evicted, "dense_scanned": scanned}

    def materialize(self):
        with self._transaction():
            return self._materialize()

    def _materialize(self):
        self.sync()
        if not self.semantic:
            raise ValueError("local embeddings are not enabled")
        count = 0
        model = self._model()
        cursor = self.db.execute("SELECT * FROM chunks WHERE id NOT IN (SELECT chunk_id FROM vectors) ORDER BY id")
        for row in cursor:
            before = time.perf_counter()
            v = model.embed([row["symbol"] + "\n" + row["text"]])[0]
            self.db.execute("INSERT INTO vectors VALUES (?,?,1,?,?)",
                            (row["id"], v, (time.perf_counter() - before) * 1000, time.time()))
            count += 1
            if count % 32 == 0:
                self._trim_cache()
        self._trim_cache()
        return {"computed": count, "cached": self.stats()["cached_vectors"]}

    def search(self, query, **options):
        # Keep source versions, chunks, vectors and provenance in one database
        # transaction. Concurrent writers wait instead of mixing generations.
        with self._transaction():
            return self._search(query, **options)

    def _search(self, query, *, token_budget=2048, limit=8, mode="auto", latency_ms=200,
               memory_kib=2048, policy=None, refresh=True):
        if not isinstance(query, str) or not query.strip() or len(query) > 8192:
            raise ValueError("query must contain 1 to 8192 characters")
        if (not isinstance(token_budget, int) or isinstance(token_budget, bool) or
                not isinstance(limit, int) or isinstance(limit, bool) or
                not 1 <= token_budget <= 1_000_000 or not 1 <= limit <= 100):
            raise ValueError("token_budget must be 1..1000000 and limit 1..100")
        start = time.perf_counter()
        freshness = self.sync() if refresh else {"status": "unchecked snapshot"}
        lex = self._lexical(query, 256)
        stats = self.stats()
        coverage = self._coverage(query, lex[0]) if lex else 0
        plan = planner.choose(query, semantic=self.semantic, coverage=coverage,
                              cache_coverage=stats["cached_vectors"] / max(1, stats["chunks"]),
                              latency_ms=latency_ms, token_budget=token_budget, chunks=stats["chunks"],
                              memory_kib=memory_kib, mode=mode, policy=policy, embed_ms=self._embed_ms)
        metrics = {"cache_hits": 0, "cache_misses": 0, "cache_evictions": 0}
        scores = {}
        pool = {r["id"]: r for r in lex[:plan["depth"]]}
        dense = {}
        if plan["strategy"] != "lexical":
            if plan["strategy"] == "semantic":
                dense, pool, extra = self._semantic_scan(query, plan["depth"], latency_ms)
            else:
                dense, extra = self._dense(query, pool.values(), time.perf_counter() + latency_ms / 1000)
            metrics.update(extra)
        lexical_ranks = {r["id"]: i for i, r in enumerate(lex)}
        semantic_ranks = {id_: i for i, (id_, sim) in enumerate(sorted(dense.items(), key=lambda x: -x[1])) if sim > 0.1}
        for id_, row in pool.items():
            if plan["strategy"] == "lexical":
                score = 1 / (1 + lexical_ranks[id_])
            elif plan["strategy"] == "semantic":
                score = dense.get(id_, -1)
                if score <= 0.1:
                    continue
            else:
                score = (1 / (60 + lexical_ranks[id_]) if id_ in lexical_ranks else 0) + (
                    1 / (60 + semantic_ranks[id_]) if id_ in semantic_ranks else 0)
            scores[id_] = score
        results, seen, used = [], set(), 0
        for id_ in sorted(scores, key=lambda k: (-scores[k], k)):
            row = pool[id_]
            signature = re.sub(r"\s+", " ", row["text"]).strip()
            if signature in seen:
                continue
            seen.add(signature)
            file = self.db.execute("SELECT digest,kind FROM files WHERE path=?", (row["path"],)).fetchone()
            item = {"path": row["path"], "start_line": row["start_line"], "end_line": row["end_line"],
                    "text": row["text"], "symbol": row["symbol"], "score": round(scores[id_], 6),
                    "revision": self._get("revision") or None, "sha256": file["digest"],
                    "line_basis": file["kind"], "evidence": {"lexical_rank": lexical_ranks.get(id_),
                    "cosine": round(dense[id_], 5) if id_ in dense else None,
                    "observed_calls": sorted({call for line, call in json.loads(row["calls"]) if line <= row["end_line"]}), "freshness": "verified" if refresh else "unchecked"}}
            # Trim by whole source lines. Charge all serialized result bytes,
            # including the provenance and evidence, against the token upper bound.
            while token_cost(json.dumps(item, ensure_ascii=False)) + used + 2 * (len(results) + 1) > token_budget:
                body = item["text"].splitlines()
                if len(body) <= 1:
                    item = None
                    break
                item["text"] = "\n".join(body[:-1])
                item["end_line"] -= 1
                item["evidence"]["observed_calls"] = sorted({call for line, call in json.loads(row["calls"])
                                                             if line <= item["end_line"]})
            if item is None:
                continue
            used += token_cost(json.dumps(item, ensure_ascii=False))
            results.append(item)
            if len(results) >= limit:
                break
        # A result array's exact serialized byte length is the reported budget cost.
        used = token_cost(json.dumps(results, ensure_ascii=False))
        metrics.update({"elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                        "tokens_used": used, "token_accounting": "UTF-8 bytes: conservative token upper bound",
                        "candidates_scored": len(scores), "semantic_coverage": metrics.get("dense_scanned", len(dense)) / max(1, stats["chunks"]),
                        "latency_target_exceeded": (time.perf_counter()-start)*1000 > latency_ms})
        if not results:
            metrics["tokens_used"] = 0  # Empty evidence consumes no context budget.
        return {"results": results, "plan": plan, "metrics": metrics, "freshness": freshness}

    def _model_storage_bytes(self):
        seen, total = set(), 0
        for path in (self.path.parent / "models").rglob("*"):
            if path.is_file():
                stat = path.stat()
                identity = (stat.st_dev, stat.st_ino)
                if identity not in seen:
                    seen.add(identity)
                    total += stat.st_size
        return total

    def stats(self):
        result = dict(self.db.execute("SELECT count(*) AS files FROM files").fetchone())
        result.update(dict(self.db.execute("SELECT count(*) AS chunks FROM chunks").fetchone()))
        result.update(dict(self.db.execute("SELECT count(*) AS cached_vectors,COALESCE(sum(length(vector)),0) "
                                           "AS cache_bytes FROM vectors").fetchone()))
        result.update({"index_bytes": self.path.stat().st_size, "cache_budget_bytes": self.cache_budget,
                       "embedding_backend": self._get("model") or ("injected" if self._embedder else "disabled"),
                       "root": str(self.root), "revision": self._get("revision") or None,
                       "model_bytes": self._model_storage_bytes()})
        return result

    def compact(self):
        self.db.commit()
        self.db.execute("INSERT INTO fts(fts) VALUES ('optimize')")
        self.db.commit()
        self.db.execute("VACUUM")

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
