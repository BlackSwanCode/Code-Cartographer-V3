"""Tests du parseur Tree-sitter."""

import pytest
from pathlib import Path
from codecartographer.parsers.tree_sitter_parser import TreeSitterParser
from codecartographer.models import SemanticPOS, Scope


class TestTreeSitterParser:
    """Tests du parseur universel."""

    @pytest.fixture
    def parser(self):
        return TreeSitterParser()

    def test_detect_language_python(self, parser):
        assert parser._detect_language(Path("test.py")) == "python"
        assert parser._detect_language(Path("test.PY")) == "python"

    def test_detect_language_javascript(self, parser):
        assert parser._detect_language(Path("test.js")) == "javascript"
        assert parser._detect_language(Path("test.mjs")) == "javascript"

    def test_detect_language_csharp(self, parser):
        assert parser._detect_language(Path("test.cs")) == "csharp"

    def test_detect_language_unknown(self, parser):
        assert parser._detect_language(Path("test.xyz")) == "unknown"

    def test_split_identifier_snake_case(self, parser):
        assert parser._split_identifier("fetch_user_data") == ["fetch", "user", "data"]

    def test_split_identifier_camel_case(self, parser):
        assert parser._split_identifier("fetchUserData") == ["fetch", "User", "Data"]

    def test_split_identifier_pascal_case(self, parser):
        assert parser._split_identifier("DataProcessor") == ["Data", "Processor"]

    def test_lemmatize_verb(self, parser):
        assert parser._lemmatize("fetching", SemanticPOS.VERB) == "fetch"
        assert parser._lemmatize("fetched", SemanticPOS.VERB) == "fetch"

    def test_lemmatize_noun(self, parser):
        assert parser._lemmatize("users", SemanticPOS.NOUN) == "user"

    def test_infer_pos_verb_prefix(self, parser):
        assert parser._infer_pos("fetch_data", "python") == SemanticPOS.VERB
        assert parser._infer_pos("is_valid", "python") == SemanticPOS.VERB

    def test_infer_pos_noun_class(self, parser):
        assert parser._infer_pos("DataProcessor", "python") == SemanticPOS.NOUN

    def test_infer_pos_pronoun(self, parser):
        assert parser._infer_pos("self", "python") == SemanticPOS.PRON
        assert parser._infer_pos("this", "javascript") == SemanticPOS.PRON

    def test_infer_semantic_role_accessor(self, parser):
        assert parser._infer_semantic_role("get_user", [], []) == "accessor"
        assert parser._infer_semantic_role("fetch_data", [], []) == "accessor"

    def test_infer_semantic_role_validator(self, parser):
        assert parser._infer_semantic_role("is_valid", [], []) == "validator"
        assert parser._infer_semantic_role("check_input", [], []) == "validator"

    def test_infer_semantic_role_factory(self, parser):
        assert parser._infer_semantic_role("create_user", [], []) == "factory"

    def test_infer_class_domain_service(self, parser):
        assert parser._infer_class_domain("UserService", []) == "service"
        assert parser._infer_class_domain("DataManager", []) == "service"

    def test_infer_class_domain_entity(self, parser):
        assert parser._infer_class_domain("UserDTO", []) == "entity"
        assert parser._infer_class_domain("OrderModel", []) == "entity"

    def test_parse_python_simple(self, parser):
        source = """
class DataProcessor:
    def process(self, data):
        return data

def main():
    processor = DataProcessor()
    result = processor.process([1, 2, 3])
"""
        module = parser.parse_file(Path("test.py"), source)

        assert module.language == "python"
        assert module.lines_total == 9
        assert len(module.functions) == 2
        assert len(module.classes) == 1
        assert module.classes[0].name == "DataProcessor"
        assert module.classes[0].semantic_domain == "domain"

    def test_parse_python_with_imports(self, parser):
        source = """
import os
import sys
from pathlib import Path
import requests

def fetch_data(url):
    return requests.get(url)
"""
        module = parser.parse_file(Path("test.py"), source)

        assert module.token_count > 0
        assert module.type_token_ratio > 0

    def test_compute_complexity_simple(self, parser):
        source = "def f(): pass"
        assert parser._compute_complexity(source, "python") == 1

    def test_compute_complexity_with_branches(self, parser):
        source = """
def f(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    else:
        return 0
"""
        assert parser._compute_complexity(source, "python") == 4

    def test_extract_calls(self, parser):
        source = "foo()\nbar(1, 2)\nfoo()"
        calls = parser._extract_calls(source, "python")
        assert "foo" in calls
        assert "bar" in calls

    def test_extract_local_vars_python(self, parser):
        source = "def f():\n    x = 1\n    y = 2"
        vars_found = parser._extract_local_vars(source, "python")
        assert "x" in vars_found
        assert "y" in vars_found
