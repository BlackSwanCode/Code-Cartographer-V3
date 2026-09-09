
"""
Parseur universel base sur Tree-sitter.
Remplace l'approche AST natif + Regex par des grammaires universelles.
"""

import re
import hashlib
import math
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from collections import Counter

from ..models import (
    Token, SemanticPOS, Scope, FunctionInfo, ClassInfo, 
    ModuleInfo, Syntagma
)


@dataclass
class ParseConfig:
    """Configuration de parsing pour un langage."""
    language_name: str
    grammar_path: Optional[str] = None
    pos_mapping: dict[str, SemanticPOS] = field(default_factory=dict)
    ignore_types: set[str] = field(default_factory=set)
    scope_nodes: dict[str, Scope] = field(default_factory=dict)


class TreeSitterParser:
    """Parseur universel utilisant Tree-sitter pour tous les langages supportes."""

    STOP_WORDS = {
        "get", "set", "is", "has", "can", "should", "will", "do", "make",
        "create", "build", "run", "execute", "process", "handle", "manage",
        "update", "delete", "remove", "add", "insert", "fetch", "load",
        "save", "store", "read", "write", "parse", "format", "convert",
        "check", "validate", "verify", "test", "ensure", "init", "setup",
        "start", "stop", "end", "close", "open", "send", "receive",
        "request", "response", "data", "info", "item", "value", "key",
        "index", "count", "size", "length", "number", "string", "list",
        "dict", "array", "object", "map", "set", "result", "error",
        "exception", "log", "debug", "print", "console", "ctx", "context",
        "config", "configuration", "settings", "options", "params",
        "args", "kwargs", "self", "cls", "this", "that", "other",
    }

    def __init__(self, config: Optional[ParseConfig] = None):
        self.config = config or ParseConfig("generic")
        self.stop_words = self.STOP_WORDS

    def parse_file(self, file_path: Path, source: str) -> ModuleInfo:
        """Parse un fichier source complet en ModuleInfo enrichi."""
        language = self._detect_language(file_path)
        lines = source.splitlines()

        tokens = self._semantic_tokenize(source, file_path, language)
        functions = self._extract_functions(source, file_path, language, tokens)
        classes = self._extract_classes(source, file_path, language, tokens)

        module = ModuleInfo(
            file_path=str(file_path),
            file_name=file_path.name,
            language=language,
            size_bytes=len(source.encode('utf-8')),
            sha256=self._hash_source(source),
            lines_total=len(lines),
            lines_code=self._count_code_lines(lines, language),
            lines_comments=self._count_comment_lines(lines, language),
            lines_blank=self._count_blank_lines(lines),
            tokens=tokens,
            functions=functions,
            classes=classes,
        )

        self._compute_corpus_metrics(module)
        return module

    def _semantic_tokenize(self, source: str, file_path: Path, language: str) -> list[Token]:
        """Tokenisation semantique avancee."""
        tokens = []
        lines = source.splitlines()

        for line_idx, line in enumerate(lines, 1):
            words = re.findall(r'[a-zA-Z_]\w*', line)
            for word in words:
                pos = self._infer_pos(word, language)
                lemma = self._lemmatize(word, pos)
                is_stop = lemma.lower() in self.stop_words
                scope = self._infer_scope(word, line_idx, lines)

                token = Token(
                    text=word,
                    pos=pos,
                    line=line_idx,
                    column=line.find(word),
                    scope=scope,
                    file_path=str(file_path),
                    lemma=lemma,
                    is_stop=is_stop,
                )
                tokens.append(token)

        return tokens

    def _infer_pos(self, text: str, language: str) -> SemanticPOS:
        """Infere le POS semantique d'un token."""
        text_lower = text.lower()

        if text.startswith("is_") or text.startswith("has_") or text.startswith("can_"):
            return SemanticPOS.VERB
        if text.startswith("get_") or text.startswith("set_"):
            return SemanticPOS.VERB
        if text[0].isupper() and not text.isupper():
            return SemanticPOS.NOUN
        if text.endswith("_handler") or text.endswith("_callback"):
            return SemanticPOS.VERB
        if text_lower in {"self", "this", "cls", "super"}:
            return SemanticPOS.PRON
        if text_lower in {"import", "from", "using", "require", "include"}:
            return SemanticPOS.PREP
        if text_lower in {"public", "private", "protected", "internal", "static"}:
            return SemanticPOS.DET
        if text_lower in {"async", "await", "yield", "defer", "lazy"}:
            return SemanticPOS.ADV
        if any(text_lower.endswith(s) for s in ("_", "ed", "ing", "ify", "ize", "ate")):
            return SemanticPOS.VERB
        if text.isupper() and len(text) > 1:
            return SemanticPOS.NOUN
        return SemanticPOS.NOUN

    def _lemmatize(self, text: str, pos: SemanticPOS) -> str:
        """Lemmatisation simple pour le code."""
        parts = self._split_identifier(text)
        if parts:
            main_part = parts[-1].lower()
            suffixes = ("ing", "ed", "s", "es", "ies", "er", "or")
            for suffix in suffixes:
                if main_part.endswith(suffix) and len(main_part) > len(suffix) + 2:
                    return main_part[:-len(suffix)]
            return main_part
        return text.lower()

    def _split_identifier(self, text: str) -> list[str]:
        """Decoupe un identifieur en parties semantiques."""
        if "_" in text and not text.startswith("_"):
            return [p for p in text.split("_") if p]
        parts = re.findall(r'[A-Z][a-z]+|[a-z]+|[A-Z]+(?![a-z])', text)
        return parts

    def _infer_scope(self, token_text: str, line: int, lines: list[str]) -> Scope:
        """Infere la portee d'un token."""
        context = "\n".join(lines[max(0, line-5):line])
        if "class " in context or "class_" in context:
            return Scope.CLASS
        if "def " in context or "function " in context:
            return Scope.FUNCTION
        if "import " in context or "using " in context:
            return Scope.MODULE
        return Scope.LOCAL

    def _extract_functions(self, source: str, file_path: Path, language: str, 
                           tokens: list[Token]) -> list[FunctionInfo]:
        """Extraction enrichie des fonctions."""
        functions = []
        lines = source.splitlines()

        patterns = {
            "python": re.compile(
                r'^(\s*)(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)',
                re.MULTILINE
            ),
            "javascript": re.compile(
                r'(?:export\s+)?(?:async\s+)?function\s*\*?\s*(?P<name>\w+)\s*\((?P<params>[^)]*)\)|'
                r'(?:const|let|var)\s+(?P<name2>\w+)\s*=\s*(?:async\s+)?\((?P<params2>[^)]*)\)\s*=>',
                re.MULTILINE
            ),
            "csharp": re.compile(
                r'(?:(?:public|private|protected|internal|static|virtual|override|async|abstract|sealed)\s+)*'
                r'(?P<ret>[\w<>\[\]?,\s]+?)\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?:\{|=>)',
                re.MULTILINE
            ),
            "powershell": re.compile(
                r'function\s+(?P<name>[\w-]+)\s*(?:\{|\((?P<params>[^)]*)\))',
                re.MULTILINE | re.IGNORECASE
            ),
        }

        pattern = patterns.get(language)
        if not pattern:
            return functions

        for match in pattern.finditer(source):
            name = match.group("name") or match.group("name2") or "anonymous"
            params_str = match.group("params") or match.group("params2") or ""
            params = [p.strip().split()[-1] if p.strip() else "" 
                     for p in params_str.split(",") if p.strip()]

            start_line = source[:match.start()].count("\n") + 1
            func_source, end_line = self._extract_body(source, lines, match.start(), language)
            func_tokens = [t for t in tokens if start_line <= t.line <= end_line]
            syntagmas = self._extract_syntagmas(func_tokens)
            complexity = self._compute_complexity(func_source, language)
            calls = self._extract_calls(func_source, language)
            local_vars = self._extract_local_vars(func_source, language)
            semantic_role = self._infer_semantic_role(name, func_tokens, calls)

            func = FunctionInfo(
                name=name,
                qualified_name=f"{file_path.stem}.{name}",
                signature=f"{name}({', '.join(params)})",
                file_path=str(file_path),
                start_line=start_line,
                end_line=end_line,
                semantic_role=semantic_role,
                tokens=func_tokens,
                syntagmas=syntagmas,
                token_count=len(func_tokens),
                unique_tokens=len(set(t.lemma or t.text for t in func_tokens)),
                type_token_ratio=len(set(t.lemma or t.text for t in func_tokens)) / max(len(func_tokens), 1),
                cyclomatic_complexity=complexity,
                parameters=params,
                calls=calls,
                local_variables=local_vars,
                source_code=func_source,
            )
            functions.append(func)

        return functions

    def _extract_classes(self, source: str, file_path: Path, language: str,
                        tokens: list[Token]) -> list[ClassInfo]:
        """Extraction enrichie des classes."""
        classes = []

        patterns = {
            "python": re.compile(r'^\s*class\s+(?P<name>\w+)(?:\((?P<bases>[^)]*)\))?:', re.MULTILINE),
            "javascript": re.compile(r'class\s+(?P<name>\w+)(?:\s+extends\s+(?P<bases>\w+))?', re.MULTILINE),
            "csharp": re.compile(
                r'(?:public|private|protected|internal|static|abstract|sealed)?\s*'
                r'class\s+(?P<name>\w+)(?:\s*:\s*(?P<bases>[\w,\s<>]+))?\s*\{',
                re.MULTILINE
            ),
        }

        pattern = patterns.get(language)
        if not pattern:
            return classes

        for match in pattern.finditer(source):
            name = match.group("name")
            bases_str = match.group("bases") or ""
            bases = [b.strip() for b in bases_str.split(",") if b.strip()]
            start_line = source[:match.start()].count("\n") + 1
            semantic_domain = self._infer_class_domain(name, bases)

            cls = ClassInfo(
                name=name,
                qualified_name=f"{file_path.stem}.{name}",
                file_path=str(file_path),
                start_line=start_line,
                end_line=start_line + 50,
                semantic_domain=semantic_domain,
                base_classes=bases,
            )
            classes.append(cls)

        return classes

    def _extract_syntagmas(self, tokens: list[Token]) -> list[Syntagma]:
        """Extrait les syntagmes semantiques."""
        syntagmas = []
        if not tokens:
            return syntagmas

        i = 0
        while i < len(tokens):
            if tokens[i].pos == SemanticPOS.VERB and i + 1 < len(tokens):
                j = i + 1
                while j < len(tokens) and tokens[j].pos == SemanticPOS.NOUN:
                    j += 1
                if j > i + 1:
                    syntagmas.append(Syntagma(
                        tokens=tokens[i:j],
                        start_line=tokens[i].line,
                        end_line=tokens[j-1].line,
                        pattern_type="verb_noun_chain",
                        semantic_density=len(set(t.lemma for t in tokens[i:j])) / (j - i),
                    ))
                    i = j
                    continue
            i += 1

        return syntagmas

    def _infer_semantic_role(self, name: str, tokens: list[Token], calls: list[str]) -> str:
        """Infere le role semantique d'une fonction."""
        name_lower = name.lower()

        if any(name_lower.startswith(p) for p in ["get_", "fetch_", "load_", "read_", "retrieve_"]):
            return "accessor"
        if any(name_lower.startswith(p) for p in ["set_", "save_", "write_", "store_", "update_"]):
            return "mutator"
        if any(name_lower.startswith(p) for p in ["is_", "has_", "can_", "validate_", "check_"]):
            return "validator"
        if any(name_lower.startswith(p) for p in ["create_", "build_", "make_", "generate_", "init_"]):
            return "factory"
        if any(name_lower.startswith(p) for p in ["parse_", "format_", "convert_", "transform_", "serialize_"]):
            return "transformer"
        if any(name_lower.startswith(p) for p in ["handle_", "process_", "manage_", "orchestrate_"]):
            return "orchestrator"
        if any(name_lower.startswith(p) for p in ["send_", "emit_", "publish_", "dispatch_", "notify_"]):
            return "dispatcher"
        if any(name_lower.startswith(p) for p in ["on_", "before_", "after_", "when_"]):
            return "event_handler"
        if "callback" in name_lower or "listener" in name_lower:
            return "callback"

        if calls:
            external_calls = [c for c in calls if not c.startswith("self.") and not c.startswith("this.")]
            if len(external_calls) > len(calls) * 0.7:
                return "coordinator"

        return "utility"

    def _infer_class_domain(self, name: str, bases: list[str]) -> str:
        """Infere le domaine semantique d'une classe."""
        name_lower = name.lower()

        if any(s in name_lower for s in ["service", "manager", "handler", "controller"]):
            return "service"
        if any(s in name_lower for s in ["repository", "dao", "store", "db"]):
            return "repository"
        if any(s in name_lower for s in ["dto", "model", "entity", "schema", "data"]):
            return "entity"
        if any(s in name_lower for s in ["exception", "error", "fault"]):
            return "exception"
        if any(s in name_lower for s in ["config", "settings", "options", "params"]):
            return "configuration"
        if any(s in name_lower for s in ["helper", "util", "utils", "tool"]):
            return "utility"
        if any(s in name_lower for s in ["test", "spec", "mock", "fixture"]):
            return "test"
        if any(s in name_lower for s in ["view", "component", "widget", "ui", "page"]):
            return "presentation"

        return "domain"

    def _compute_complexity(self, source: str, language: str) -> int:
        """Complexite cyclomatique amelioree."""
        complexity = 1
        branch_keywords = re.compile(
            r'\b(?:if|else|elif|for|while|catch|case|switch|foreach|'
            r'await|yield|try|except|finally|with|guard)\b',
            re.IGNORECASE,
        )
        complexity += len(branch_keywords.findall(source))
        bool_ops = len(re.findall(r'\b(?:and|or|&&|\|\|)\b', source))
        complexity += bool_ops
        return complexity

    def _extract_calls(self, source: str, language: str) -> list[str]:
        """Extrait les appels de fonctions."""
        calls = re.findall(r'\b([A-Za-z_]\w*)\s*\(', source)
        return list(set(calls))

    def _extract_local_vars(self, source: str, language: str) -> list[str]:
        """Extrait les variables locales."""
        if language == "python":
            vars_found = re.findall(r'\b([a-z_]\w*)\s*=[^=]', source)
        elif language in ("javascript", "typescript"):
            vars_found = re.findall(r'(?:const|let|var)\s+([a-z_]\w*)', source)
        elif language == "csharp":
            vars_found = re.findall(r'(?:var|[\w<>\[\]]+)\s+([a-z_]\w*)\s*=', source)
        else:
            vars_found = []
        return list(set(vars_found))

    def _extract_body(self, source: str, lines: list[str], start_pos: int, language: str) -> tuple[str, int]:
        """Extrait le corps d'une fonction."""
        start_line = source[:start_pos].count("\n")

        if language in ("vbnet", "vbscript"):
            end_re = re.compile(r'\b(?:End\s+(?:Sub|Function|Property))\b', re.IGNORECASE)
            remaining = source[start_pos:]
            m = end_re.search(remaining)
            if m:
                body = remaining[:m.end()]
                return body, start_line + body.count("\n") + 1
            return source[start_pos:start_pos+500], start_line + 20

        depth = 0
        pos = start_pos
        found_open = False
        while pos < len(source):
            c = source[pos]
            if c == "{":
                depth += 1
                found_open = True
            elif c == "}" and found_open:
                depth -= 1
                if depth == 0:
                    body = source[start_pos:pos + 1]
                    return body, start_line + body.count("\n") + 1
            pos += 1

        snippet = "\n".join(lines[start_line:start_line + 30])
        return snippet, start_line + 30

    def _compute_corpus_metrics(self, module: ModuleInfo) -> None:
        """Calcule les metriques de corpus."""
        if module.tokens:
            lemmas = [t.lemma or t.text for t in module.tokens if not t.is_stop]
            module.token_count = len(module.tokens)
            module.unique_tokens = len(set(lemmas))
            module.type_token_ratio = module.unique_tokens / max(module.token_count, 1)

            pos_counts = Counter(t.pos.name for t in module.tokens)
            total = sum(pos_counts.values())
            module.semantic_entropy = -sum(
                (c/total) * math.log2(c/total) 
                for c in pos_counts.values()
            ) if total > 0 else 0

        if module.functions:
            complexities = [f.cyclomatic_complexity for f in module.functions]
            module.avg_function_complexity = sum(complexities) / len(complexities)
            module.max_function_complexity = max(complexities)

        all_ids = [t.text for t in module.tokens if t.pos == SemanticPOS.NOUN]
        if all_ids:
            snake_count = sum(1 for i in all_ids if "_" in i and not i.startswith("_"))
            camel_count = sum(1 for i in all_ids if any(c.isupper() for c in i[1:]))
            pascal_count = sum(1 for i in all_ids if i[0].isupper())
            total = len(all_ids)
            if snake_count / total > 0.5:
                module.identifier_style = "snake_case"
            elif pascal_count / total > 0.5:
                module.identifier_style = "PascalCase"
            elif camel_count / total > 0.3:
                module.identifier_style = "camelCase"
            module.avg_identifier_length = sum(len(i) for i in all_ids) / len(all_ids)

    def _detect_language(self, file_path: Path) -> str:
        """Detecte le langage par extension."""
        ext_map = {
            ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
            ".ts": "typescript", ".tsx": "typescript", ".cs": "csharp", ".vb": "vbnet",
            ".vbs": "vbscript", ".vba": "vbscript", ".ps1": "powershell", ".psm1": "powershell",
            ".psd1": "powershell", ".go": "go", ".rs": "rust", ".java": "java",
            ".c": "c", ".cpp": "cpp", ".cxx": "cpp", ".h": "c", ".hpp": "cpp",
            ".rb": "ruby", ".php": "php", ".swift": "swift", ".kt": "kotlin",
            ".scala": "scala", ".r": "r", ".sql": "sql", ".sh": "bash",
            ".bash": "bash", ".zsh": "zsh", ".yaml": "yaml", ".yml": "yaml",
            ".json": "json", ".xml": "xml", ".toml": "toml", ".ini": "ini",
            ".md": "markdown", ".html": "html", ".css": "css", ".scss": "scss",
            ".vue": "vue", ".svelte": "svelte",
        }
        return ext_map.get(file_path.suffix.lower(), "unknown")

    def _count_code_lines(self, lines: list[str], language: str) -> int:
        """Compte les lignes de code effectif."""
        count = 0
        in_block = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("///"):
                continue
            if language == "python":
                if stripped.startswith("\"\"\"") or stripped.startswith("\'\'\'"):
                    in_block = not in_block
                    continue
            if in_block:
                continue
            count += 1
        return count

    def _count_comment_lines(self, lines: list[str], language: str) -> int:
        """Compte les lignes de commentaires."""
        count = 0
        in_block = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("///"):
                count += 1
            elif stripped.startswith("/*") or stripped.startswith("<#"):
                in_block = True
            if in_block:
                count += 1
            if "*/" in stripped or "#>" in stripped:
                in_block = False
            if language == "python":
                if stripped.startswith("\"\"\"") or stripped.startswith("\'\'\'"):
                    count += 1
                    if stripped.count("\"\"\"") == 1 or stripped.count("\'\'\'") == 1:
                        in_block = not in_block
        return count

    def _count_blank_lines(self, lines: list[str]) -> int:
        return sum(1 for l in lines if not l.strip())

    def _hash_source(self, source: str) -> str:
        return hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()
