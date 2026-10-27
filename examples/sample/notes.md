# Sample engineering notes

The expiring cache uses a monotonic clock. It removes expired entries on read.
A deadline from a wall clock could break after system clock adjustments.

## Retry behavior

Transient I/O errors get exponential backoff. The caller's last error is raised
when the retry budget is exhausted. Authentication failures should not be retried.

## Privacy

This sample contains only fictional code and notes. RAVEL never sends indexed
source text to a remote service. Embeddings run locally when explicitly enabled.
