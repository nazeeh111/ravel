import json

import pytest

from ravel.planner import choose, train


def call(query='retry_operation', **options):
    args = dict(semantic=True, coverage=1, cache_coverage=0.5, latency_ms=200, token_budget=2048, chunks=100)
    args.update(options)
    return choose(query, **args)


def test_routes_and_budgets():
    assert call()['strategy'] == 'lexical'
    assert call('where does the code discard old values', coverage=0.1)['strategy'] == 'semantic'
    assert call('retry failed operation', coverage=0.7)['strategy'] == 'hybrid'
    assert call(latency_ms=1)['strategy'] == 'lexical'
    assert call('why failed', coverage=0.3, semantic=False)['strategy'] == 'lexical'
    assert call('why failed', coverage=0.3, memory_kib=16)['depth'] <= 2
    assert call('why failed', coverage=0.1, cache_coverage=0)['depth'] <= call('why failed', coverage=0.1, cache_coverage=1)['depth']
    with pytest.raises(ValueError):
        call(memory_kib=0)


def test_learned_policy_training_and_validation(tmp_path):
    rows = [{'features':[1, 0.1, 1, 0.5, 0.2, 0.5], 'action':'lexical'}] * 8
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps(train(rows)))
    result = call(policy=policy)
    assert result['strategy'] == 'lexical'
    assert result['policy'] == 'learned'
    policy.write_text('{"features":[]}')
    with pytest.raises(ValueError, match='incompatible'):
        call(policy=policy)


def test_nonfinite_budgets_rejected():
    from ravel.server import validate_search
    for value in [float('nan'), float('inf'), float('-inf'), 10**400]:
        with pytest.raises(ValueError, match='finite'):
            call(latency_ms=value)
        with pytest.raises(ValueError, match='finite'):
            validate_search({'query': 'x', 'latency_ms': value})
        with pytest.raises(ValueError, match='finite'):
            call(memory_kib=value)


def test_partial_cold_semantic_preserves_lexical_candidates():
    result = call('an obscure task with some lexical matches', coverage=0.2, cache_coverage=0, chunks=5000)
    assert result['strategy'] == 'hybrid'
    assert 'preserve lexical' in result['reason']
    assert call('no match at all', coverage=0, cache_coverage=0, chunks=5000)['strategy'] == 'semantic'
