"""Tests des analyseurs corpus."""

import pytest
import math
from codecartographer.analyzers.corpus_analyzers import (
    StylometricAnalyzer, SemanticNetworkAnalyzer, EntropyAnalyzer
)
from codecartographer.corpus.store import CorpusStore
from codecartographer.models import (
    Token, SemanticPOS, Scope, FunctionInfo, ModuleInfo
)


class TestEntropyAnalyzer:
    """Tests de l'analyse d'entropie."""

    @pytest.fixture
    def store(self):
        store = CorpusStore()

        # Module avec distribution uniforme de POS
        module = ModuleInfo(
            file_path="test.py",
            file_name="test.py",
            language="python",
            tokens=[
                Token(text="def", pos=SemanticPOS.VERB, line=1, column=0,
                     scope=Scope.GLOBAL, file_path="test.py"),
                Token(text="x", pos=SemanticPOS.NOUN, line=1, column=4,
                     scope=Scope.GLOBAL, file_path="test.py"),
                Token(text="if", pos=SemanticPOS.BLOCK, line=2, column=0,
                     scope=Scope.GLOBAL, file_path="test.py"),
                Token(text="return", pos=SemanticPOS.VERB, line=3, column=0,
                     scope=Scope.GLOBAL, file_path="test.py"),
            ],
            functions=[],
            classes=[],
        )
        store.insert_module(module)
        return store

    def test_shannon_entropy(self, store):
        analyzer = EntropyAnalyzer(store)
        entropy = analyzer.compute_shannon_entropy("test.py")

        # Entropie maximale pour 4 symboles équiprobables = 2 bits
        assert 0 <= entropy <= 2

    def test_semantic_density(self, store):
        analyzer = EntropyAnalyzer(store)
        density = analyzer.compute_semantic_density("test.py")

        assert density >= 0


class TestSemanticNetworkAnalyzer:
    """Tests du réseau sémantique."""

    @pytest.fixture
    def store_with_cooccurrence(self):
        store = CorpusStore()

        # Tokens avec co-occurrences
        tokens = []
        for i in range(10):
            tokens.append(Token(text="fetch", pos=SemanticPOS.VERB, line=i, column=0,
                              scope=Scope.GLOBAL, file_path="test.py"))
            tokens.append(Token(text="data", pos=SemanticPOS.NOUN, line=i, column=10,
                              scope=Scope.GLOBAL, file_path="test.py"))

        module = ModuleInfo(
            file_path="test.py",
            file_name="test.py",
            language="python",
            tokens=tokens,
            functions=[],
            classes=[],
        )
        store.insert_module(module)
        return store

    def test_build_cooccurrence_network(self, store_with_cooccurrence):
        analyzer = SemanticNetworkAnalyzer(store_with_cooccurrence)
        graph = analyzer.build_cooccurrence_network(min_weight=1)

        assert graph.number_of_nodes() >= 2
        assert graph.number_of_edges() >= 1

    def test_find_key_concepts(self, store_with_cooccurrence):
        analyzer = SemanticNetworkAnalyzer(store_with_cooccurrence)
        graph = analyzer.build_cooccurrence_network(min_weight=1)
        concepts = analyzer.find_key_concepts(graph, top_n=5)

        assert len(concepts) > 0
        assert all(isinstance(score, float) for _, score in concepts)


class TestStylometricAnalyzer:
    """Tests de la stylométrie."""

    @pytest.fixture
    def store(self):
        return CorpusStore()

    def test_compute_lexical_complexity(self, store):
        # Module simple
        module = ModuleInfo(
            file_path="test.py",
            file_name="test.py",
            language="python",
            tokens=[
                Token(text="def", pos=SemanticPOS.VERB, line=1, column=0,
                     scope=Scope.GLOBAL, file_path="test.py"),
                Token(text="process", pos=SemanticPOS.VERB, line=1, column=4,
                     scope=Scope.GLOBAL, file_path="test.py", lemma="process"),
                Token(text="data", pos=SemanticPOS.NOUN, line=1, column=12,
                     scope=Scope.GLOBAL, file_path="test.py", lemma="data"),
            ],
            functions=[],
            classes=[],
        )
        store.insert_module(module)

        analyzer = StylometricAnalyzer(store)
        complexity = analyzer.compute_lexical_complexity("test.py")

        assert complexity["total_tokens"] == 2  # sans stop words
        assert complexity["unique_types"] == 2
        assert complexity["ttr"] == 1.0
