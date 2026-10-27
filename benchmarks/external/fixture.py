"""Independent hand-authored fixture. No engine internals or generated queries at runtime."""

from pathlib import Path
import json

TOPICS = [
    (
        "retry",
        "retry_request",
        "Retry failed HTTP requests with exponential backoff and random jitter. Stop after the maximum number of attempts. Honor Retry-After on rate limiting.",
        "How do requests recover after temporary network failures?",
        "retry_request",
    ),
    (
        "lease",
        "renew_lease",
        "Renew an expiring distributed lock lease while the owner is alive. Refuse renewal when another owner holds the lock.",
        "Where is ownership of a distributed lock extended?",
        "renew_lease",
    ),
    (
        "invoice",
        "calculate_invoice",
        "Calculate invoice totals using decimal arithmetic. Add item costs, apply a percentage discount, then compute sales tax. Round monetary values to two decimal places.",
        "How are discounts and tax included in a bill?",
        "calculate_invoice",
    ),
    (
        "session",
        "expire_session",
        "Invalidate an authentication session when its idle timeout is exceeded. Remove the bearer token and require the user to sign in again.",
        "What removes idle login sessions?",
        "expire_session",
    ),
    (
        "snapshot",
        "save_snapshot",
        "Save a consistent database snapshot to a temporary file. Flush data to disk, then atomically rename it to prevent partially written backups.",
        "How are backups protected against interrupted writes?",
        "save_snapshot",
    ),
    (
        "queue",
        "drain_queue",
        "Drain pending work from a bounded job queue before shutdown. Reject new jobs after closing starts and wait for running jobs to finish.",
        "What happens to pending jobs during graceful shutdown?",
        "drain_queue",
    ),
    (
        "checksum",
        "verify_checksum",
        "Verify the integrity of a downloaded artifact using its SHA256 checksum. Refuse installation when the expected digest does not match.",
        "Where are corrupted downloaded packages rejected?",
        "verify_checksum",
    ),
    (
        "pagination",
        "paginate_cursor",
        "Fetch database records in stable cursor order. Use the last record identifier as the continuation token instead of an offset.",
        "How can a client continue reading the next page of records?",
        "paginate_cursor",
    ),
    (
        "redaction",
        "redact_secrets",
        "Redact access tokens, passwords and private keys before writing diagnostic logs. Preserve non-sensitive context for troubleshooting.",
        "Where are credentials removed from diagnostics?",
        "redact_secrets",
    ),
    (
        "throttle",
        "consume_bucket",
        "Consume a token from a rate-limit bucket. Refill tokens according to elapsed time and deny traffic when the bucket is empty.",
        "How is excessive incoming traffic limited?",
        "consume_bucket",
    ),
    (
        "dedup",
        "deduplicate_events",
        "Deduplicate webhook events by their idempotency key. Remember completed event identifiers and avoid repeating side effects.",
        "What prevents repeated webhook delivery from applying an operation twice?",
        "deduplicate_events",
    ),
    (
        "unicode",
        "normalize_name",
        "Normalize user-visible names to Unicode NFC. Preserve case for display while comparing a case-folded key for uniqueness.",
        "How are equivalent international names compared?",
        "normalize_name",
    ),
    (
        "cache",
        "evict_cache",
        "Evict the least recently used cache entries until the byte limit is satisfied. Update access timestamps after each cache hit.",
        "Which cached values are removed when storage fills up?",
        "evict_cache",
    ),
    (
        "routing",
        "select_replica",
        "Route database reads to healthy replicas with the shortest replication lag. Fall back to the primary when no replica is healthy.",
        "Where do database reads go if every replica is unavailable?",
        "select_replica",
    ),
    (
        "upload",
        "assemble_upload",
        "Assemble file uploads from individually verified chunks. Support resuming interrupted transfers without sending completed chunks again.",
        "How can an interrupted large file transfer resume?",
        "assemble_upload",
    ),
    (
        "transaction",
        "rollback_transaction",
        "Roll back a transaction when any statement fails. Release locks and restore the database state before returning the original error.",
        "What restores data after a database operation fails?",
        "rollback_transaction",
    ),
]


def make(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for stem, symbol, text, _, _ in TOPICS:
        (root / (stem + ".md")).write_text(f"# {stem.title()}\n\n{text}\n\nImplementation: `{symbol}`.\n")
        (root / (stem + ".py")).write_text(f'def {symbol}(value):\n    """{text}"""\n    return value\n')
    return [
        {"query": q, "relevant": [s + ".md", s + ".py"], "kind": "natural"} for s, _, _, q, _ in TOPICS
    ] + [{"query": q, "relevant": [s + ".md", s + ".py"], "kind": "identifier"} for s, _, _, _, q in TOPICS]


if __name__ == "__main__":
    import sys

    queries = make(sys.argv[1])
    print(json.dumps(queries, indent=2))
