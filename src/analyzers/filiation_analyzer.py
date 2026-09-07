"""
Analyse de filiation logicielle.

Implémente les méthodologies décrites dans xAnalyse-theorie.txt / xAnalyse-tools.txt :

    1. Analyse statique multi-niveaux (lexicale -> syntaxique -> architecturale)
    2. Détection de clones (Types I à IV, cf. Roy & Cordy)
    3. Métriques de similarité (Levenshtein, Jaccard, cosinus)
    4. Program/Code Dependence Graph simplifié (PDG-lite)
    5. Analyse des familles d'identifiants (analyse linguistique appliquée au code)
    6. Détection de motifs architecturaux (Design/Architectural Patterns)
    7. Classification de filiation (Niveaux A/B/C/D : copie, fork, réécriture, convergence)

Aucune des méthodes n'est probante isolément (cf. §15/§18 des deux documents) ;
c'est la convergence d'un faisceau d'indices qui permet de formuler une
hypothèse de filiation argumentée. Ce module ne prétend jamais démontrer
l'auteur, l'antériorité ou l'intention — seulement des relations structurelles
plausibles entre unités de code.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Optional

from ..models import (
    CloneMatch, CloneType, SimilarityReport, IdentifierFamily,
    ArchitecturePattern, FiliationVerdict, FiliationLevel,
    ProgramDependenceGraph, DependencyGraphNode, DependencyGraphEdgePDG,
)
from ..corpus.store import CorpusStore


# ---------------------------------------------------------------------------
# 0. Primitives de similarité (§4 xAnalyse-theorie : Levenshtein / Jaccard / cosinus)
# ---------------------------------------------------------------------------

def levenshtein_distance(a: str, b: str) -> int:
    """Distance de Levenshtein classique (programmation dynamique).

    Réservée aux chaînes courtes (identifiants, signatures) : le coût est
    O(len(a) * len(b)). Pour des séquences longues, `levenshtein_ratio`
    utilise un algorithme de blocs correspondants équivalent en pratique.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current[j] = min(
                previous[j] + 1,        # suppression
                current[j - 1] + 1,     # insertion
                previous[j - 1] + cost  # substitution
            )
        previous = current
    return previous[-1]


def levenshtein_ratio(a: str, b: str) -> float:
    """Similarité normalisée [0,1] entre deux chaînes.

    Pour les chaînes courtes (<= 200 caractères), utilise la vraie distance
    de Levenshtein. Au-delà, bascule sur `SequenceMatcher` (ratio de blocs
    correspondants), équivalent pratique et bien plus rapide sur du code
    source complet.
    """
    if not a and not b:
        return 1.0
    if len(a) <= 200 and len(b) <= 200:
        dist = levenshtein_distance(a, b)
        return 1.0 - dist / max(len(a), len(b))
    return SequenceMatcher(None, a, b).ratio()


def jaccard_similarity(a: set, b: set) -> float:
    """Similarité de Jaccard J(A,B) = |A ∩ B| / |A ∪ B| (§4)."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def cosine_similarity(v1: Counter, v2: Counter) -> float:
    """Similarité cosinus entre deux vecteurs de fréquences (§4)."""
    if not v1 or not v2:
        return 0.0
    keys = set(v1) | set(v2)
    dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in keys)
    norm1 = math.sqrt(sum(val * val for val in v1.values()))
    norm2 = math.sqrt(sum(val * val for val in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def longest_common_subsequence_ratio(a: list, b: list) -> float:
    """Ratio LCS(a,b) / max(len(a), len(b)) — utilisé pour comparer des
    séquences symboliques (rôles sémantiques, pipelines d'architecture)."""
    if not a or not b:
        return 0.0
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[n][m] / max(n, m)


# ---------------------------------------------------------------------------
# 1. Normalisation de code (§3 xAnalyse-tools : Types I / II de clones)
# ---------------------------------------------------------------------------

# Mots-clés multi-langages à préserver lors de l'alpha-renommage (Type II).
# Volontairement large et approximatif : l'objectif est heuristique, pas
# une analyse syntaxique complète (cf. §18 "Limites").
_KEYWORDS = {
    "if", "else", "elif", "for", "while", "return", "break", "continue",
    "def", "function", "class", "import", "from", "as", "try", "except",
    "catch", "finally", "raise", "throw", "with", "yield", "async", "await",
    "let", "const", "var", "new", "delete", "public", "private", "protected",
    "static", "void", "int", "string", "bool", "float", "double", "self",
    "this", "super", "true", "false", "none", "null", "nil", "and", "or",
    "not", "in", "is", "switch", "case", "default", "do", "struct", "enum",
    "interface", "implements", "extends", "package", "namespace", "using",
    "fn", "impl", "match", "pub", "mod", "func", "defer", "go", "chan",
}

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_COMMENT_PREFIXES = ("#", "//", "*", "/*", "--")


def normalize_type1(source: str) -> str:
    """Normalisation Type I : supprime espaces, lignes vides, commentaires.

    Seuls changent, entre deux clones Type I : les espaces et les commentaires
    (§3 Détection de clones, xAnalyse-theorie).
    """
    lines = []
    for raw in source.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith(_COMMENT_PREFIXES):
            continue
        # supprime un commentaire de fin de ligne naïvement (heuristique)
        for marker in ("//", "#"):
            idx = stripped.find(f" {marker} ")
            if idx != -1:
                stripped = stripped[:idx].strip()
        lines.append(" ".join(stripped.split()))
    return "\n".join(lines)


def alpha_rename(normalized_source: str) -> str:
    """Normalisation Type II : renomme les identifiants en positions
    canoniques (ID0, ID1, ...), en préservant les mots-clés du langage.

    Exemple : ``mutate(genome)`` et ``mutate(sequence)`` deviennent tous deux
    ``ID0(ID1)`` si la logique environnante est identique (§3 Type II).
    """
    mapping: dict[str, str] = {}

    def repl(match: re.Match) -> str:
        ident = match.group(0)
        if ident.lower() in _KEYWORDS:
            return ident
        if ident not in mapping:
            mapping[ident] = f"ID{len(mapping)}"
        return mapping[ident]

    return _IDENTIFIER_RE.sub(repl, normalized_source)


def extract_identifiers(source: str) -> list[str]:
    """Extrait la séquence des identifiants (hors mots-clés) d'un extrait."""
    return [
        tok for tok in _IDENTIFIER_RE.findall(source)
        if tok.lower() not in _KEYWORDS
    ]


# ---------------------------------------------------------------------------
# 2. Détection de clones (§3 xAnalyse-theorie / §4,§13 xAnalyse-tools)
# ---------------------------------------------------------------------------

@dataclass
class _FuncRow:
    qualified_name: str
    name: str
    file_path: str
    source_code: str
    calls: list[str]
    semantic_role: Optional[str]
    cyclomatic_complexity: int
    token_count: int


class CloneDetector:
    """Détecteur de clones de code, opérant sur les fonctions du corpus.

    Combine plusieurs niveaux de normalisation pour discriminer les quatre
    types de clones décrits dans la littérature (Roy & Cordy) et repris dans
    xAnalyse-theorie.txt §3 :

        Type I   -> texte identique hors forme (espaces/commentaires)
        Type II  -> identifiants renommés, logique identique
        Type III -> ajouts/suppressions mineurs, structure conservée
        Type IV  -> comportement équivalent, code très différent
    """

    # Seuils de décision (heuristiques, ajustables)
    TYPE1_THRESHOLD = 0.98
    TYPE2_THRESHOLD = 0.92
    TYPE3_THRESHOLD = 0.72
    TYPE4_BEHAVIOR_THRESHOLD = 0.65
    MIN_TOKEN_COUNT = 12  # évite le bruit des fonctions triviales (getters, etc.)

    def __init__(self, store: CorpusStore):
        self.store = store

    def _load_functions(self) -> list[_FuncRow]:
        import json
        rows = self.store.conn.execute("""
            SELECT qualified_name, name, file_path, source_code, calls,
                   semantic_role, cyclomatic_complexity, token_count
            FROM functions
            WHERE token_count >= ?
        """, [self.MIN_TOKEN_COUNT]).fetchall()

        out = []
        for qname, name, fpath, src, calls_json, role, cc, tcount in rows:
            calls = json.loads(calls_json) if calls_json else []
            out.append(_FuncRow(qname, name, fpath, src or "", calls, role, cc or 1, tcount or 0))
        return out

    def compare_pair(self, fa: _FuncRow, fb: _FuncRow) -> CloneMatch:
        """Compare deux fonctions et détermine le type de clone le plus fort."""
        norm_a, norm_b = normalize_type1(fa.source_code), normalize_type1(fb.source_code)
        type1_score = levenshtein_ratio(norm_a, norm_b) if norm_a and norm_b else 0.0

        renamed_a, renamed_b = alpha_rename(norm_a), alpha_rename(norm_b)
        type2_score = levenshtein_ratio(renamed_a, renamed_b) if renamed_a and renamed_b else 0.0

        # Type III : similarité de séquence tolérante aux insertions/suppressions
        type3_score = SequenceMatcher(None, renamed_a, renamed_b).ratio() if renamed_a and renamed_b else 0.0

        # Type IV : similarité comportementale — même rôle, séquences d'appels
        # proches, complexité comparable, mais peu de similarité textuelle.
        call_jaccard = jaccard_similarity(set(fa.calls), set(fb.calls))
        role_match = 1.0 if (fa.semantic_role and fa.semantic_role == fb.semantic_role) else 0.0
        cc_closeness = 1.0 - min(abs(fa.cyclomatic_complexity - fb.cyclomatic_complexity) /
                                  max(fa.cyclomatic_complexity, fb.cyclomatic_complexity, 1), 1.0)
        behavioral_score = (call_jaccard * 0.5) + (role_match * 0.3) + (cc_closeness * 0.2)

        # Décision : le type le plus fort qui dépasse son seuil l'emporte,
        # du plus strict (I) au plus lâche (IV).
        clone_type = CloneType.NONE
        similarity = max(type1_score, type2_score, type3_score, behavioral_score)

        if type1_score >= self.TYPE1_THRESHOLD:
            clone_type = CloneType.TYPE_I
        elif type2_score >= self.TYPE2_THRESHOLD:
            clone_type = CloneType.TYPE_II
        elif type3_score >= self.TYPE3_THRESHOLD:
            clone_type = CloneType.TYPE_III
        elif behavioral_score >= self.TYPE4_BEHAVIOR_THRESHOLD and type3_score < self.TYPE3_THRESHOLD:
            clone_type = CloneType.TYPE_IV

        evidence = []
        if clone_type != CloneType.NONE:
            evidence.append(f"texte normalisé: {type1_score:.2f}")
            evidence.append(f"après alpha-renommage: {type2_score:.2f}")
            evidence.append(f"séquence tolérante: {type3_score:.2f}")
            if clone_type == CloneType.TYPE_IV:
                evidence.append(f"jaccard(appels)={call_jaccard:.2f}, même rôle={bool(role_match)}, "
                                 f"complexité proche={cc_closeness:.2f}")

        return CloneMatch(
            function_a=fa.qualified_name, function_b=fb.qualified_name,
            file_a=fa.file_path, file_b=fb.file_path,
            clone_type=clone_type, similarity=similarity,
            type1_score=type1_score, type2_score=type2_score,
            type3_score=type3_score, behavioral_score=behavioral_score,
            evidence=evidence,
        )

    def detect_all(self, exclude_same_file: bool = False) -> list[CloneMatch]:
        """Détecte tous les clones du corpus.

        Pour limiter la complexité combinatoire (O(n²)), les fonctions sont
        d'abord regroupées par plage de taille (bucket ±30% de token_count) :
        deux clones Types I-III ont nécessairement une taille très proche.
        Les clones Type IV purement comportementaux à taille très différente
        échappent à cette optimisation par construction (cas rare et hors
        du périmètre visé ici, cf. §18 Limites).
        """
        functions = self._load_functions()
        buckets: dict[int, list[_FuncRow]] = defaultdict(list)
        for f in functions:
            # bucket logarithmique : regroupe les tailles comparables
            bucket_key = int(math.log1p(f.token_count) * 4)
            buckets[bucket_key].append(f)
            buckets[bucket_key - 1].append(f)  # chevauchement pour tolérance
            buckets[bucket_key + 1].append(f)

        seen_pairs = set()
        matches = []
        for bucket_funcs in buckets.values():
            for fa, fb in combinations(bucket_funcs, 2):
                if fa.qualified_name == fb.qualified_name:
                    continue
                if exclude_same_file and fa.file_path == fb.file_path:
                    continue
                pair_key = tuple(sorted((fa.qualified_name, fb.qualified_name)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                match = self.compare_pair(fa, fb)
                if match.clone_type != CloneType.NONE:
                    matches.append(match)

        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches


# ---------------------------------------------------------------------------
# 3. Similarité inter-fichiers (§4/§13 : identifiants, imports, concepts)
# ---------------------------------------------------------------------------

class SimilarityEngine:
    """Similarité multi-métrique entre fichiers (ou tout couple d'entités
    identifiées par leur ``file_path``)."""

    WEIGHTS = {
        "levenshtein": 0.20,
        "jaccard_identifiers": 0.25,
        "jaccard_imports": 0.15,
        "jaccard_concepts": 0.15,
        "cosine": 0.25,
    }

    def __init__(self, store: CorpusStore):
        self.store = store

    def _file_identifiers(self, file_path: str) -> set[str]:
        rows = self.store.conn.execute("""
            SELECT name FROM functions WHERE file_path = ?
            UNION ALL
            SELECT name FROM classes WHERE file_path = ?
        """, [file_path, file_path]).fetchall()
        return {r[0] for r in rows if r[0]}

    def _file_imports(self, file_path: str) -> set[str]:
        import json
        row = self.store.conn.execute("""
            SELECT external_dependencies, internal_dependencies FROM modules WHERE file_path = ?
        """, [file_path]).fetchone()
        if not row:
            return set()
        ext = json.loads(row[0] or "[]")
        internal = json.loads(row[1] or "[]")
        return set(ext) | set(internal)

    def _file_lemma_vector(self, file_path: str) -> Counter:
        rows = self.store.conn.execute("""
            SELECT lemma, COUNT(*) FROM tokens
            WHERE file_path = ? AND is_stop = FALSE AND lemma IS NOT NULL
            GROUP BY lemma
        """, [file_path]).fetchall()
        return Counter({r[0]: r[1] for r in rows})

    def _identifier_sequence_text(self, file_path: str) -> str:
        rows = self.store.conn.execute("""
            SELECT name FROM functions WHERE file_path = ? ORDER BY start_line
        """, [file_path]).fetchall()
        return " ".join(r[0] for r in rows if r[0])

    def compare_files(self, file_a: str, file_b: str) -> SimilarityReport:
        ids_a, ids_b = self._file_identifiers(file_a), self._file_identifiers(file_b)
        imp_a, imp_b = self._file_imports(file_a), self._file_imports(file_b)
        vec_a, vec_b = self._file_lemma_vector(file_a), self._file_lemma_vector(file_b)
        seq_a, seq_b = self._identifier_sequence_text(file_a), self._identifier_sequence_text(file_b)

        report = SimilarityReport(
            entity_a=file_a, entity_b=file_b,
            levenshtein_ratio=levenshtein_ratio(seq_a, seq_b),
            jaccard_identifiers=jaccard_similarity(ids_a, ids_b),
            jaccard_imports=jaccard_similarity(imp_a, imp_b),
            jaccard_concepts=jaccard_similarity(set(vec_a), set(vec_b)),
            cosine_tokens=cosine_similarity(vec_a, vec_b),
        )
        report.composite_score = sum(
            getattr(report, {
                "levenshtein": "levenshtein_ratio",
                "jaccard_identifiers": "jaccard_identifiers",
                "jaccard_imports": "jaccard_imports",
                "jaccard_concepts": "jaccard_concepts",
                "cosine": "cosine_tokens",
            }[k]) * w
            for k, w in self.WEIGHTS.items()
        )
        return report

    def compare_all_files(self) -> list[SimilarityReport]:
        files = [r[0] for r in self.store.conn.execute("SELECT file_path FROM modules").fetchall()]
        reports = []
        for a, b in combinations(sorted(files), 2):
            reports.append(self.compare_files(a, b))
        reports.sort(key=lambda r: r.composite_score, reverse=True)
        return reports


# ---------------------------------------------------------------------------
# 4. Program Dependence Graph simplifié — PDG-lite (§5/§6 xAnalyse-theorie)
# ---------------------------------------------------------------------------

# Mots-clés de contrôle multi-langages -> utilisés pour repérer les branches
_CONTROL_KEYWORDS = {
    "if", "elif", "else", "for", "while", "switch", "case", "try",
    "except", "catch", "match",
}
_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*[\w\[\]\., ]+)?\s*=(?!=)")
_CALL_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")


class DependencyGraphBuilder:
    """Construit un PDG-lite par fonction : un graphe de contrôle séquentiel
    enrichi d'arêtes de données (def -> use) et d'appels.

    Ce n'est pas un CPG/PDG au sens de Joern/CodeQL (§6), mais une
    approximation langage-agnostique suffisante pour comparer la *forme*
    structurelle de deux fonctions indépendamment de leurs noms.
    """

    def build(self, qualified_name: str, source_code: str) -> ProgramDependenceGraph:
        pdg = ProgramDependenceGraph(function_qualified_name=qualified_name)
        lines = [l for l in source_code.splitlines() if l.strip()]

        defined_at: dict[str, str] = {}
        prev_node_id: Optional[str] = None

        for i, line in enumerate(lines):
            node_id = f"n{i}"
            stripped = line.strip()
            first_word = re.match(r"[A-Za-z_]+", stripped)
            keyword = first_word.group(0).lower() if first_word else ""

            kind = "stmt"
            if keyword in _CONTROL_KEYWORDS:
                kind = "branch"
            elif _ASSIGN_RE.match(line):
                kind = "def"
            elif _CALL_RE.search(line):
                kind = "call"

            pdg.nodes.append(DependencyGraphNode(id=node_id, label=stripped[:60], kind=kind, line=i))

            # Dépendance de contrôle : lien séquentiel (proxy de CFG linéaire)
            if prev_node_id is not None:
                pdg.edges.append(DependencyGraphEdgePDG(prev_node_id, node_id, kind="control"))
            prev_node_id = node_id

            # Dépendance de données : def -> use
            assign_match = _ASSIGN_RE.match(line)
            if assign_match:
                var = assign_match.group(1)
                defined_at[var] = node_id

            for used_var in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", line):
                if used_var in defined_at and defined_at[used_var] != node_id:
                    pdg.edges.append(DependencyGraphEdgePDG(defined_at[used_var], node_id, kind="data"))

        return pdg

    @staticmethod
    def compare(pdg_a: ProgramDependenceGraph, pdg_b: ProgramDependenceGraph) -> float:
        """Similarité structurelle entre deux PDG-lite, indépendante des noms.

        Compare les vecteurs d'invariants (nb nœuds/arêtes par nature) via
        cosinus — une vraie distance d'édition de graphe (Graph Edit Distance,
        §16 Références) serait plus précise mais coûteuse ; ce proxy est
        suffisant pour classer les paires candidates (§7 Analyse des graphes).
        """
        return cosine_similarity(Counter(pdg_a.signature_vector), Counter(pdg_b.signature_vector))


# ---------------------------------------------------------------------------
# 5. Familles d'identifiants (§9 xAnalyse-theorie / §6-7 xAnalyse-tools)
# ---------------------------------------------------------------------------

class IdentifierFamilyAnalyzer:
    """Regroupe les identifiants (classes, fonctions) en familles lexicales.

    Exemple type (§9) : Genome / GlyphDNA / SyntheticGenome / OrganismGenome
    forment une famille conceptuelle repérable par similarité de sous-chaînes
    et d'édition, même sans emprunter le même préfixe.
    """

    def __init__(self, store: CorpusStore, min_similarity: float = 0.55, min_family_size: int = 2):
        self.store = store
        self.min_similarity = min_similarity
        self.min_family_size = min_family_size

    def _split_identifier(self, name: str) -> set[str]:
        """Décompose un identifiant en "morphèmes" (camelCase / snake_case)."""
        parts = re.split(r"_|(?<=[a-z0-9])(?=[A-Z])", name)
        return {p.lower() for p in parts if len(p) > 2}

    def _load_identifiers(self) -> list[tuple[str, str]]:
        rows = self.store.conn.execute("""
            SELECT name, file_path FROM functions
            UNION ALL
            SELECT name, file_path FROM classes
        """).fetchall()
        return [(r[0], r[1]) for r in rows if r[0] and len(r[0]) > 2]

    def detect_families(self) -> list[IdentifierFamily]:
        identifiers = self._load_identifiers()
        names = sorted({n for n, _ in identifiers})
        files_by_name: dict[str, set[str]] = defaultdict(set)
        for n, f in identifiers:
            files_by_name[n].add(f)

        # Union-find pour regrouper les identifiants apparentés
        parent = {n: n for n in names}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        morphemes = {n: self._split_identifier(n) for n in names}

        for a, b in combinations(names, 2):
            # Lien fort : morphème (racine lexicale) partagé, ex: "genome"
            shared_morphemes = morphemes[a] & morphemes[b]
            lexical_hit = bool(shared_morphemes)
            edit_similarity = levenshtein_ratio(a.lower(), b.lower())

            if lexical_hit or edit_similarity >= self.min_similarity:
                union(a, b)

        groups: dict[str, list[str]] = defaultdict(list)
        for n in names:
            groups[find(n)].append(n)

        families = []
        for i, (_, members) in enumerate(groups.items()):
            if len(members) < self.min_family_size:
                continue
            # racine représentative = morphème le plus fréquent dans la famille
            morph_counter = Counter()
            for m in members:
                morph_counter.update(morphemes[m])
            root = morph_counter.most_common(1)[0][0] if morph_counter else members[0]

            pair_scores = [levenshtein_ratio(a.lower(), b.lower()) for a, b in combinations(members, 2)]
            cohesion = sum(pair_scores) / len(pair_scores) if pair_scores else 1.0

            family_files = set()
            for m in members:
                family_files |= files_by_name[m]

            families.append(IdentifierFamily(
                id=f"fam_{i}", root=root, members=sorted(members),
                files=sorted(family_files), cohesion=cohesion,
            ))

        families.sort(key=lambda f: len(f.members), reverse=True)
        return families


# ---------------------------------------------------------------------------
# 6. Motifs architecturaux (§8/§13 xAnalyse-theorie, §12/§15 xAnalyse-tools)
# ---------------------------------------------------------------------------

# Pipelines canoniques évoqués dans les deux documents source. Chaque étape
# est une liste de rôles sémantiques (cf. FunctionInfo.semantic_role) ou de
# mots-clés de nom de fonction qui peuvent l'incarner.
CANONICAL_PIPELINES: dict[str, list[str]] = {
    "etat_transformation_evaluation": ["accessor", "transformer", "validator", "mutator"],
    "entree_analyse_transformation_evaluation_export": [
        "accessor", "validator", "transformer", "validator", "dispatcher",
    ],
    "pipeline_orchestre": ["orchestrator", "transformer", "validator", "dispatcher"],
}


class ArchitecturePatternAnalyzer:
    """Détecte les motifs architecturaux récurrents (§8) à partir de la
    séquence des rôles sémantiques des fonctions d'un module, et compare
    l'architecture implicite de deux fichiers entre eux (§13/§15)."""

    def __init__(self, store: CorpusStore):
        self.store = store

    def role_sequence(self, file_path: str) -> list[str]:
        rows = self.store.conn.execute("""
            SELECT semantic_role FROM functions
            WHERE file_path = ? ORDER BY start_line
        """, [file_path]).fetchall()
        # dé-duplique les répétitions consécutives (une architecture est une
        # séquence d'étapes, pas un histogramme de rôles)
        seq = []
        for (role,) in rows:
            if not role:
                continue
            if not seq or seq[-1] != role:
                seq.append(role)
        return seq

    def match_canonical(self, file_path: str) -> list[ArchitecturePattern]:
        seq = self.role_sequence(file_path)
        patterns = []
        for name, stages in CANONICAL_PIPELINES.items():
            score = longest_common_subsequence_ratio(seq, stages)
            if score >= 0.5:
                patterns.append(ArchitecturePattern(
                    name=name, stages=stages, files_matched=[file_path], confidence=score,
                ))
        return patterns

    def compare_architectures(self, file_a: str, file_b: str) -> float:
        """Similarité architecturale entre deux fichiers (LCS des rôles)."""
        seq_a, seq_b = self.role_sequence(file_a), self.role_sequence(file_b)
        return longest_common_subsequence_ratio(seq_a, seq_b)

    def detect_all(self) -> list[ArchitecturePattern]:
        files = [r[0] for r in self.store.conn.execute("SELECT file_path FROM modules").fetchall()]
        by_pattern: dict[str, ArchitecturePattern] = {}
        for f in files:
            for pattern in self.match_canonical(f):
                if pattern.name not in by_pattern:
                    by_pattern[pattern.name] = pattern
                else:
                    by_pattern[pattern.name].files_matched.append(f)
                    by_pattern[pattern.name].confidence = max(by_pattern[pattern.name].confidence, pattern.confidence)
        return sorted(by_pattern.values(), key=lambda p: len(p.files_matched), reverse=True)


# ---------------------------------------------------------------------------
# 7. Classification de filiation (§14 xAnalyse-theorie, §13 xAnalyse-tools)
# ---------------------------------------------------------------------------

class FiliationClassifier:
    """Combine clones, similarité, architecture et vocabulaire pour proposer
    un niveau de filiation (A/B/C/D) entre deux fichiers, avec un faisceau
    d'indices explicite plutôt qu'un score opaque (cf. §17 Heuristiques :
    "une filiation est retenue uniquement lorsqu'un ensemble cohérent
    d'indices converge").

    Rappel des limites (§15/§18) : ceci ne démontre ni l'auteur, ni
    l'antériorité, ni l'intention — seulement des hypothèses structurelles.
    """

    def __init__(self, store: CorpusStore):
        self.store = store
        self.clone_detector = CloneDetector(store)
        self.similarity_engine = SimilarityEngine(store)
        self.architecture_analyzer = ArchitecturePatternAnalyzer(store)

    def _function_count(self, file_path: str) -> int:
        return self.store.conn.execute(
            "SELECT COUNT(*) FROM functions WHERE file_path = ?", [file_path]
        ).fetchone()[0]

    def classify_pair(self, file_a: str, file_b: str,
                       clone_matches: Optional[list[CloneMatch]] = None) -> FiliationVerdict:
        if clone_matches is None:
            all_clones = self.clone_detector.detect_all()
            clone_matches = [
                c for c in all_clones
                if {c.file_a, c.file_b} == {file_a, file_b}
            ]

        n_a, n_b = self._function_count(file_a), self._function_count(file_b)
        strict_clones = [c for c in clone_matches if c.clone_type in (CloneType.TYPE_I, CloneType.TYPE_II)]
        loose_clones = [c for c in clone_matches if c.clone_type in (CloneType.TYPE_III, CloneType.TYPE_IV)]

        core_ratio = len(strict_clones) / max(min(n_a, n_b), 1)
        loose_ratio = (len(strict_clones) + len(loose_clones)) / max(min(n_a, n_b), 1)

        similarity = self.similarity_engine.compare_files(file_a, file_b)
        arch_similarity = self.architecture_analyzer.compare_architectures(file_a, file_b)
        size_ratio = max(n_a, n_b) / max(min(n_a, n_b), 1)

        evidence = {
            "core_clone_ratio": round(core_ratio, 3),
            "loose_clone_ratio": round(loose_ratio, 3),
            "composite_similarity": round(similarity.composite_score, 3),
            "jaccard_identifiers": round(similarity.jaccard_identifiers, 3),
            "jaccard_concepts": round(similarity.jaccard_concepts, 3),
            "architecture_similarity": round(arch_similarity, 3),
            "size_ratio": round(size_ratio, 3),
        }
        rationale = []

        level = FiliationLevel.UNRELATED
        confidence = 0.0

        # Niveau A — Copie directe : noyau quasi-identique, peu ou pas d'enrichissement
        if core_ratio >= 0.8 and similarity.composite_score >= 0.8:
            level = FiliationLevel.A_COPY
            confidence = (core_ratio + similarity.composite_score) / 2
            rationale.append(f"{len(strict_clones)} clone(s) Type I/II sur un noyau commun "
                              f"(ratio={core_ratio:.2f}), similarité globale {similarity.composite_score:.2f}.")

        # Niveau B — Fork : noyau commun clair, mais l'un enrichit nettement l'autre
        elif core_ratio >= 0.45 and size_ratio >= 1.25 and arch_similarity >= 0.6:
            level = FiliationLevel.B_FORK
            confidence = (core_ratio + arch_similarity) / 2
            larger = file_a if n_a > n_b else file_b
            rationale.append(f"Noyau commun détecté (ratio={core_ratio:.2f}) ; {larger} comporte "
                              f"~{size_ratio:.1f}x plus de fonctions — probable enrichissement (fork).")

        # Niveau C — Réécriture : architecture proche, peu/pas de clones textuels
        elif arch_similarity >= 0.65 and core_ratio < 0.3 and similarity.jaccard_concepts >= 0.25:
            level = FiliationLevel.C_REWRITE
            confidence = (arch_similarity + similarity.jaccard_concepts) / 2
            rationale.append(f"Séquence de rôles sémantiques proche (LCS={arch_similarity:.2f}) malgré "
                              f"peu de clones textuels (ratio={core_ratio:.2f}) — probable réécriture "
                              f"conservant l'architecture.")

        # Niveau D — Convergence : motif partagé mais vocabulaire indépendant
        elif 0.35 <= arch_similarity < 0.65 and similarity.jaccard_concepts < 0.2 and loose_ratio < 0.15:
            level = FiliationLevel.D_CONVERGENCE
            confidence = arch_similarity
            rationale.append(f"Motif architectural partiellement partagé (LCS={arch_similarity:.2f}) "
                              f"mais vocabulaire quasi disjoint (Jaccard concepts={similarity.jaccard_concepts:.2f}) "
                              f"— convergence probable vers un patron commun plutôt qu'une filiation directe.")

        else:
            rationale.append("Aucun faisceau d'indices suffisant pour établir une filiation "
                              "(cf. §17 xAnalyse-tools : convergence requise de plusieurs critères).")

        return FiliationVerdict(
            file_a=file_a, file_b=file_b, level=level,
            confidence=round(confidence, 3), evidence=evidence, rationale=rationale,
        )

    def classify_corpus(self) -> list[FiliationVerdict]:
        """Classifie toutes les paires de fichiers du corpus.

        Les clones sont calculés une seule fois puis répartis par paire de
        fichiers, afin d'éviter de relancer CloneDetector à chaque paire.
        """
        files = [r[0] for r in self.store.conn.execute("SELECT file_path FROM modules").fetchall()]
        all_clones = self.clone_detector.detect_all(exclude_same_file=True)

        clones_by_pair: dict[tuple, list[CloneMatch]] = defaultdict(list)
        for c in all_clones:
            key = tuple(sorted((c.file_a, c.file_b)))
            clones_by_pair[key].append(c)

        verdicts = []
        for a, b in combinations(sorted(files), 2):
            key = tuple(sorted((a, b)))
            verdict = self.classify_pair(a, b, clone_matches=clones_by_pair.get(key, []))
            if verdict.level != FiliationLevel.UNRELATED:
                verdicts.append(verdict)

        verdicts.sort(key=lambda v: v.confidence, reverse=True)
        return verdicts
