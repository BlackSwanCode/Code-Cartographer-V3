"""
CodeCartographer v2.0 — Analyseur de corpus de code source

Approche linguistique de corpus appliquée au développement logiciel.
"""

__version__ = "2.0.0"
__author__ = "CodeCartographer Team"

from .models import (
    Token, SemanticPOS, Scope, FunctionInfo, ClassInfo,
    ModuleInfo, CorpusIndex, ConcordanceLine
)
from .parsers.tree_sitter_parser import TreeSitterParser, ParseConfig
from .corpus.store import CorpusStore
from .analyzers.corpus_analyzers import (
    StylometricAnalyzer,
    SemanticNetworkAnalyzer,
    DiachronicAnalyzer,
    EntropyAnalyzer,
)

__all__ = [
    "Token", "SemanticPOS", "Scope",
    "FunctionInfo", "ClassInfo", "ModuleInfo",
    "CorpusIndex", "ConcordanceLine",
    "TreeSitterParser", "ParseConfig",
    "CorpusStore",
    "StylometricAnalyzer",
    "SemanticNetworkAnalyzer",
    "DiachronicAnalyzer",
    "EntropyAnalyzer",
]
