"""Tests du stockage corpus."""

import pytest
from pathlib import Path
from codecartographer.corpus.store import CorpusStore
from codecartographer.models import (
    Token, SemanticPOS, Scope, FunctionInfo, ClassInfo, ModuleInfo
)


class TestCorpusStore:
    """Tests de la base DuckDB."""

    @pytest.fixture
    def store(self):
        return CorpusStore()  # Base en mémoire

    @pytest.fixture
    def sample_module(self):
        return ModuleInfo(
            file_path="test.py",
            file_name="test.py",
            language="python",
            size_bytes=100,
            sha256="abc123",
            lines_total=10,
            lines_code=8,
            lines_comments=1,
            lines_blank=1,
            tokens=[
                Token(text="def", pos=SemanticPOS.VERB, line=1, column=0,
                     scope=Scope.GLOBAL, file_path="test.py"),
                Token(text="fetch", pos=SemanticPOS.VERB, line=1, column=4,
                     scope=Scope.GLOBAL, file_path="test.py", lemma="fetch"),
                Token(text="data", pos=SemanticPOS.NOUN, line=1, column=10,
                     scope=Scope.GLOBAL, file_path="test.py", lemma="data"),
            ],
            functions=[
                FunctionInfo(
                    name="fetch_data",
                    qualified_name="test.fetch_data",
                    signature="fetch_data(url)",
                    file_path="test.py",
                    start_line=1,
                    end_line=3,
                    semantic_role="accessor",
                    token_count=3,
                    unique_tokens=3,
                    type_token_ratio=1.0,
                    cyclomatic_complexity=1,
                    parameters=["url"],
                    calls=["requests.get"],
                    local_variables=["response"],
                    source_code="def fetch_data(url):\n    return requests.get(url)",
                )
            ],
            classes=[
                ClassInfo(
                    name="DataService",
                    qualified_name="test.DataService",
                    file_path="test.py",
                    start_line=5,
                    end_line=10,
                    semantic_domain="service",
                )
            ],
        )

    def test_insert_module(self, store, sample_module):
        module_id = store.insert_module(sample_module)
        assert module_id is not None

        # Vérification
        result = store.conn.execute("SELECT COUNT(*) FROM modules").fetchone()
        assert result[0] == 1

        result = store.conn.execute("SELECT COUNT(*) FROM tokens").fetchone()
        assert result[0] == 3

        result = store.conn.execute("SELECT COUNT(*) FROM functions").fetchone()
        assert result[0] == 1

        result = store.conn.execute("SELECT COUNT(*) FROM classes").fetchone()
        assert result[0] == 1

    def test_frequency_list(self, store, sample_module):
        store.insert_module(sample_module)

        freq = store.get_frequency_list(by_lemma=True)
        assert len(freq) > 0

        # "fetch" et "data" devraient être présents
        words = [w for w, _ in freq]
        assert "fetch" in words or "data" in words

    def test_vocabulary_profile(self, store, sample_module):
        store.insert_module(sample_module)

        profile = store.get_vocabulary_profile()
        assert profile["total_tokens"] > 0
        assert profile["unique_lemmas"] > 0
        assert 0 < profile["type_token_ratio"] <= 1

    def test_concordance(self, store, sample_module):
        store.insert_module(sample_module)

        concordances = store.query_concordance("fetch", context=2)
        assert len(concordances) > 0
        assert concordances[0].keyword == "fetch"

    def test_ngrams(self, store, sample_module):
        store.insert_module(sample_module)

        ngrams = store.query_ngrams(n=2, min_freq=1)
        assert isinstance(ngrams, list)

    def test_export_parquet(self, store, sample_module, tmp_path):
        store.insert_module(sample_module)

        output_dir = tmp_path / "parquet"
        store.export_to_parquet(output_dir)

        assert (output_dir / "modules.parquet").exists()
        assert (output_dir / "tokens.parquet").exists()
