from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from ravel import Index
from ravel.embeddings import cosine, pack
from ravel.sources import chunks


class TinyEmbedder:
    """Deterministic unit-test fake, never used for performance/quality claims."""
    def embed(self, texts, query=False):
        return [pack([float('retry' in t.lower()), float('cache' in t.lower()), 0.1]) for t in texts]


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'retry.py').write_text('def retry_operation():\n    """Retry failed requests."""\n    return 42\n')
    (tmp_path / 'notes.md').write_text('# Cache\nCache stored values and remove expired entries.\n')
    return tmp_path


def test_incremental_edits_deletes_renames_and_same_stat(project):
    with Index(project) as idx:
        assert idx.sync()['changed'] == 2
        assert idx.sync()['changed'] == 0
        assert idx.search('retry_operation')['results'][0]['symbol'] == 'retry_operation'
        p = project / 'retry.py'
        stat = p.stat()
        original = p.read_text()
        p.write_text(original.replace('42', '99'))
        os.utime(p, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        result = idx.search('retry_operation')['results'][0]
        assert 'return 99' in result['text']
        assert result['sha256'] != __import__('hashlib').sha256(original.encode()).hexdigest()
        p.rename(project / 'new.py')
        assert idx.search('retry_operation')['results'][0]['path'] == 'new.py'
        (project / 'new.py').unlink()
        assert not idx.search('retry_operation')['results']
        assert idx.db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert idx.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission semantics")
def test_ignore_privacy_permissions_and_binary(project):
    (project / '.env').write_text('not opened')
    (project / 'credentials.json').write_text('{"do_not_read":true}')
    (project / 'nested').mkdir()
    (project / 'nested' / '.gitignore').write_text('*.md\n!public.md\n')
    (project / 'nested' / 'private.md').write_text('secretcanary')
    (project / 'nested' / 'public.md').write_text('allowedcanary')
    (project / '.ravelignore').write_text('ignored/\n')
    (project / 'ignored').mkdir()
    (project / 'ignored' / 'x.md').write_text('ignorecanary')
    (project / 'binary.txt').write_bytes(b'\x00bad')
    (project / 'inline.txt').write_text('-----BEGIN PRIVATE KEY-----\nexample')
    (project / 'noaccess.txt').write_text('permissioncanary')
    (project / 'noaccess.txt').chmod(0o000)
    try:
        with Index(project) as idx:
            idx.sync()
            paths = {r[0] for r in idx.db.execute('SELECT path FROM files')}
            assert paths == {'retry.py', 'notes.md', 'nested/public.md'}
            assert not idx.search('secretcanary')['results']
            (project / 'notes.md').chmod(0)
            assert not idx.search('expired')['results']
    finally:
        (project / 'noaccess.txt').chmod(0o600)
        (project / 'notes.md').chmod(0o600)


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires platform privilege")
def test_symlinks_are_excluded_and_db_symlink_refused(project, tmp_path_factory):
    outside = tmp_path_factory.mktemp('outside')
    (outside / 'private.txt').write_text('outsidecanary')
    (project / 'link.txt').symlink_to(outside / 'private.txt')
    (project / 'folder').symlink_to(outside, target_is_directory=True)
    with Index(project) as idx:
        assert not idx.search('outsidecanary')['results']
    (project / '.linked').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        Index(project, db_path=project / '.linked' / 'index.sqlite3')


def test_source_spans_exact_and_no_invented_relationships(project):
    source = '@decorate\nclass Client:\n    def fetch(self):\n        return helper()\n\ndef helper():\n    return 1\n'
    (project / 'client.py').write_text(source)
    with Index(project) as idx:
        rows = idx.search('fetch', token_budget=10000)['results']
        function = next(r for r in rows if r['symbol'] == 'Client.fetch')
        assert function['text'] == '\n'.join(source.splitlines()[function['start_line']-1:function['end_line']])
        assert function['evidence']['observed_calls'] == ['helper']
        assert 'resolved_dependencies' not in function['evidence']
    slices = chunks(source, '.py')
    assert any(c.symbol == 'Client' and c.start == 1 for c in slices)


def test_token_upper_bound_and_budget_truncation(project):
    (project / 'unicode.md').write_text('\n'.join(['Context 世界 ' + str(i) for i in range(40)]), encoding='utf-8')
    with Index(project) as idx:
        for budget in [1, 32, 500, 800, 2048, 10000]:
            result = idx.search('Context', token_budget=budget)
            if result['results']:
                assert len(json.dumps(result['results'], ensure_ascii=False).encode()) <= budget
                for r in result['results']:
                    assert r['end_line'] - r['start_line'] + 1 == len(r['text'].splitlines())
            assert result['metrics']['tokens_used'] <= budget


def test_cache_bounded_and_invalidated(project):
    with Index(project, embedder=TinyEmbedder(), cache_bytes=20) as idx:
        result = idx.search('retry', mode='semantic', latency_ms=5000, token_budget=10000)
        assert result['metrics']['cache_misses'] > 0
        assert idx.stats()['cache_bytes'] <= 20
        result = idx.search('retry', mode='semantic', latency_ms=5000, token_budget=10000)
        assert result['metrics']['cache_hits'] > 0
        (project / 'retry.py').unlink()
        idx.sync()
        assert not idx.db.execute('SELECT 1 FROM vectors JOIN chunks ON chunk_id=id WHERE path=?', ('retry.py',)).fetchone()
    with Index(project, embedder=TinyEmbedder(), cache_bytes=0) as idx:
        idx.search('cache', mode='hybrid', latency_ms=5000)
        assert idx.stats()['cached_vectors'] == 0


def test_quantized_cosine():
    a, b = pack([1., 0., -1.]), pack([0., 1., 0.])
    assert cosine(a, a) == pytest.approx(1, abs=1e-6)
    assert cosine(a, b) == 0
    assert len(a) == 7


def test_phrase_punctuation_and_validation(project):
    with Index(project) as idx:
        assert idx.search('"remove expired"')['results']
        assert not idx.search('"expired remove"')['results']
        assert idx.search('" OR * NOT: [] "')['results'] == []
        for bad in ['', ' ']:
            with pytest.raises(ValueError):
                idx.search(bad)
        with pytest.raises(ValueError):
            idx.search('cache', mode='semantic')
        with pytest.raises(ValueError):
            idx.search('cache', token_budget=-1)


def test_git_branch_freshness(project):
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    subprocess.run(['git', '-C', str(project), 'add', 'retry.py', 'notes.md'], check=True)
    subprocess.run(['git', '-C', str(project), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
    with Index(project) as idx:
        original = idx.search('retry_operation')['results'][0]['revision']
        subprocess.run(['git', '-C', str(project), 'checkout', '-qb', 'changed'], check=True)
        (project / 'retry.py').write_text('def branch_operation():\n    return 7\n')
        subprocess.run(['git', '-C', str(project), 'add', 'retry.py'], check=True)
        subprocess.run(['git', '-C', str(project), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'branch'], check=True)
        result = idx.search('branch_operation')['results'][0]
        assert result['revision'] != original
        assert all('retry_operation' not in r['text'] for r in idx.search('retry_operation')['results'])


def test_snapshot_label_and_root_binding(project, tmp_path_factory):
    with Index(project) as idx:
        idx.sync()
        result = idx.search('cache', refresh=False)
        assert result['freshness']['status'] == 'unchecked snapshot'
        assert result['results'][0]['evidence']['freshness'] == 'unchecked'
        db = idx.path
    with pytest.raises(ValueError, match='different source root'):
        Index(tmp_path_factory.mktemp('other'), db_path=db)


def test_cli_mcp_wire(project):
    messages = [
        {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
        {'jsonrpc':'2.0','id':2,'method':'tools/list'},
        {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'ravel_search','arguments':{'query':'retry_operation'}}},
        {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'ravel_search','arguments':{'query':'x','root':'/'}}},
    ]
    proc = subprocess.run([sys.executable, '-m', 'ravel', 'mcp', '--root', str(project)],
                          input='\n'.join(map(json.dumps, messages)) + '\n', capture_output=True, text=True, check=True)
    responses = list(map(json.loads, proc.stdout.splitlines()))
    assert len(responses) == 4
    assert responses[0]['result']['protocolVersion'] == '2025-06-18'
    assert responses[1]['result']['tools'][0]['name'] == 'ravel_search'
    assert json.loads(responses[2]['result']['content'][0]['text'])['results'][0]['symbol'] == 'retry_operation'
    assert responses[3]['result']['isError'] is True
    assert proc.stderr == ''


def test_lowered_quota_persists_for_lexical_search(project):
    with Index(project, embedder=TinyEmbedder(), cache_bytes=100) as idx:
        idx.search('retry', mode='semantic', latency_ms=5000)
        assert idx.stats()['cache_bytes'] > 0
    with Index(project, cache_bytes=0) as idx:
        idx.search('retry')
        assert idx.stats()['cache_bytes'] == 0
    with Index(project) as idx:
        assert idx.stats()['cache_budget_bytes'] == 0


def test_repeated_phrase_and_snippet_calls(project):
    (project / 'repeat.md').write_text('repeat repeat once in order\n')
    (project / 'scopes.py').write_text('def outer():\n    def inner():\n        sensitive_call()\n    inner()\n')
    with Index(project) as idx:
        assert not idx.search('"once once"')['results']
        assert idx.search('"repeat repeat"')['results']
        rows = idx.search('outer', token_budget=10000)['results']
        for r in rows:
            if r['path'] == 'scopes.py':
                for call in r['evidence']['observed_calls']:
                    assert call + '(' in r['text']


def test_cli_root_is_honored(project, tmp_path_factory):
    unrelated = tmp_path_factory.mktemp('unrelated')
    proc = subprocess.run([sys.executable, '-m', 'ravel', 'index', '--root', str(project), '--json'],
                          cwd=unrelated, capture_output=True, text=True, check=True)
    assert json.loads(proc.stdout)['stats']['root'] == str(project.resolve())
    assert not (unrelated / '.ravel').exists()


def test_concurrent_update_cannot_mix_provenance(project):
    import hashlib
    import threading
    import time
    with Index(project) as idx:
        idx.sync()
        old_text = (project / 'retry.py').read_bytes()
        original = idx._lexical
        start = threading.Event()
        finished = threading.Event()
        failures = []
        def writer():
            try:
                start.wait(5)
                (project / 'retry.py').write_text('def replacement():\n    return 99\n')
                with Index(project) as other:
                    other.sync()
                finished.set()
            except Exception as exc:
                failures.append(exc)
        def hooked(query, depth):
            rows = original(query, depth)
            start.set()
            time.sleep(0.1)
            assert not finished.is_set()
            return rows
        idx._lexical = hooked
        thread = threading.Thread(target=writer)
        thread.start()
        result = idx.search('retry_operation')['results'][0]
        assert result['sha256'] == hashlib.sha256(old_text).hexdigest()
        assert 'return 42' in result['text']
        idx._lexical = original
        thread.join(5)
        assert not failures
        assert finished.is_set()
        assert 'replacement' in idx.search('replacement')['results'][0]['text']


def test_malformed_documents_do_not_abort_healthy_sources(project):
    pytest.importorskip('pypdf')
    pytest.importorskip('docx')
    (project / 'broken.pdf').write_bytes(b'not a PDF')
    (project / 'broken.docx').write_bytes(b'not a ZIP')
    from docx import Document
    doc = Document()
    doc.add_paragraph('Documentcanary proof of extracted provenance')
    doc.save(project / 'valid.docx')
    with Index(project) as idx:
        assert idx.search('retry_operation')['results']
        hit = idx.search('Documentcanary')['results'][0]
        assert hit['line_basis'] == 'docx-extracted'
        assert hit['start_line'] == 1
        assert 'broken.pdf' not in {r[0] for r in idx.db.execute('SELECT path FROM files')}


def test_materialization_serializes_source_generations(project):
    import threading
    import time
    started, done = threading.Event(), threading.Event()
    failures = []
    class PausingEmbedder(TinyEmbedder):
        def embed(self, texts, query=False):
            started.set()
            time.sleep(0.1)
            assert not done.is_set()
            return super().embed(texts, query=query)
    def writer():
        try:
            started.wait(5)
            (project / 'retry.py').write_text('def newer():\n    return 8\n')
            with Index(project) as other:
                other.sync()
            done.set()
        except Exception as exc:
            failures.append(exc)
    with Index(project, embedder=PausingEmbedder()) as idx:
        thread = threading.Thread(target=writer)
        thread.start()
        idx.materialize()
        thread.join(5)
        assert done.is_set() and not failures
        assert not idx.db.execute('SELECT 1 FROM vectors JOIN chunks ON chunk_id=id WHERE path=?', ('retry.py',)).fetchone()


def test_pdf_errors_do_not_log_source_bytes(project, capsys, caplog):
    pytest.importorskip('pypdf')
    (project / 'bad.pdf').write_bytes(b'private-header-canary')
    with Index(project) as idx:
        idx.sync()
    captured = capsys.readouterr()
    assert 'priva' not in captured.err
    assert 'priva' not in caplog.text


def test_pdf_cold_process_does_not_log_bytes(project):
    pytest.importorskip('pypdf')
    (project / 'bad.pdf').write_bytes(b'synthetic-private-canary')
    proc = subprocess.run([sys.executable, '-m', 'ravel', 'index', '--root', str(project), '--json'],
                          capture_output=True, text=True, check=True)
    assert 'synth' not in proc.stderr
    assert proc.stderr == ''


def test_utf8_cli_and_mcp_under_legacy_codepage(project):
    (project / 'unicode.md').write_text('Context 世界 content\n', encoding='utf-8')
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'cp1252'
    proc = subprocess.run([sys.executable, '-m', 'ravel', 'search', 'Context', '--root', str(project), '--json'],
                          env=env, capture_output=True, check=True)
    assert '世界' in json.loads(proc.stdout.decode('utf-8'))['results'][0]['text']
    message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': 'ravel_search', 'arguments': {'query': '世界'}}}
    proc = subprocess.run([sys.executable, '-m', 'ravel', 'mcp', '--root', str(project)], env=env,
                          input=(json.dumps(message, ensure_ascii=False)+'\n').encode('utf-8'), capture_output=True, check=True)
    result = json.loads(proc.stdout.decode('utf-8'))['result']
    assert result['isError'] is False
    assert '世界' in json.loads(result['content'][0]['text'])['results'][0]['text']
