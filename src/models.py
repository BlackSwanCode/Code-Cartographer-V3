"""
Structures de données centrales pour l'analyse de corpus de code source.
Inspirées des standards de la linguistique de corpus (TEI, CoNLL-U, etc.)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Any
from pathlib import Path


# ---------------------------------------------------------------------------
# Enums sémantiques (POS-tagging adapté au code)
# ---------------------------------------------------------------------------

class SemanticPOS(Enum):
    """Part-of-Speech tagging sémantique pour le code source.

    Analogie linguistique:
        VERB      -> Fonction/méthode (action)
        NOUN      -> Variable/classe (entité)
        ADJ       -> Type hint, modificateur
        ADV       -> Async, decorator, flag
        PREP      -> Import, using, require
        CONJ      -> And, or, pipe operators
        PRON      -> Self, this, super
        DET       -> Access modifiers (public, private)
        NUM       -> Literals numériques
        STR       -> Strings, docstrings
        COMMENT   -> Métadiscours
    """
    VERB = auto()           # Fonction, méthode, action
    NOUN = auto()           # Variable, classe, struct
    ADJ = auto()            # Type hint, qualifier
    ADV = auto()            # Modificateur de comportement
    PREP = auto()           # Import, dependency
    CONJ = auto()           # Opérateur logique, chain
    PRON = auto()           # Référence self/this
    DET = auto()            # Déterminant d'accès
    NUM = auto()            # Literal numérique
    STR = auto()            # Literal chaîne
    COMMENT = auto()        # Métadiscours
    BLOCK = auto()          # Structure de contrôle
    UNKNOWN = auto()


class Scope(Enum):
    """Portée sémantique des entités."""
    GLOBAL = "global"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    LOCAL = "local"
    PARAMETER = "parameter"
    CLOSURE = "closure"


class DependencyType(Enum):
    """Type de dépendance entre entités."""
    IMPORT = "import"           # Import explicite
    CALL = "call"               # Appel de fonction
    INHERIT = "inherit"         # Héritage
    IMPLEMENT = "implement"     # Implémentation
    USE = "use"                 # Utilisation de variable
    RETURN = "return"           # Retour de type
    THROW = "throw"             # Exception
    COMPOSE = "compose"         # Composition


# ---------------------------------------------------------------------------
# Entités atomiques du corpus
# ---------------------------------------------------------------------------

@dataclass
class Token:
    """Token sémantique — unité minimale du corpus de code.

    Équivalent linguistique: le token en NLP, mais avec une sémantique
    de programmation (pas seulement lexical).
    """
    text: str                           # Texte brut
    pos: SemanticPOS                    # Catégorie sémantique
    line: int                           # Ligne dans le source
    column: int                         # Colonne
    scope: Scope                        # Portée
    file_path: str                      # Fichier source

    # Attributs linguistiques enrichis
    lemma: Optional[str] = None          # Forme canonique
    stem: Optional[str] = None           # Racine (sans suffixes type _handler)
    is_stop: bool = False              # Mot-outil (get, set, is, has)

    # Attributs de programmation
    is_external: bool = False          # Dépendance externe
    is_builtin: bool = False           # Builtin du langage
    frequency_in_file: int = 1         # Fréquence locale

    # Métadonnées flexibles
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass 
class Syntagma:
    """Syntagme — séquence de tokens formant une unité sémantique.

    Équivalent: le syntagme en linguistique (groupe nominal, verbal).
    Exemple: "fetch_user_data()" = [VERB:fetch] + [NOUN:user] + [NOUN:data]
    """
    tokens: list[Token]
    start_line: int
    end_line: int

    # Type de syntagme
    pattern_type: Optional[str] = None   # e.g., "verb_noun_chain", "get_set_pair"

    # Métriques
    semantic_density: float = 0.0       # Concepts uniques / tokens total
    abstraction_level: float = 0.0      # 0=concret, 1=abstrait

    @property
    def text(self) -> str:
        return " ".join(t.text for t in self.tokens)

    @property
    def lemmas(self) -> list[str]:
        return [t.lemma or t.text for t in self.tokens]


@dataclass
class SemanticNode:
    """Nœud dans le réseau sémantique du corpus.

    Représente un concept (pas seulement un symbole) qui peut apparaître
    sous différents noms dans différents fichiers.
    """
    id: str                             # UUID stable
    canonical_name: str                 # Nom canonique (lemmatisé)
    aliases: list[str] = field(default_factory=list)  # Synonymes détectés
    pos: SemanticPOS = SemanticPOS.NOUN

    # Propriétés sémantiques
    domain: Optional[str] = None        # Domaine métier (auth, payment, etc.)
    is_core_concept: bool = False      # Concept central du codebase

    # Réseau
    related_concepts: list[str] = field(default_factory=list)  # IDs
    cooccurrence_score: dict[str, float] = field(default_factory=dict)

    # Distribution
    files_present: list[str] = field(default_factory=list)
    frequency_total: int = 0


@dataclass
class DependencyEdge:
    """Arête dans le graphe de dépendances sémantiques."""
    source_id: str                      # ID du nœud source
    target_id: str                      # ID du nœud cible
    dep_type: DependencyType
    weight: float = 1.0                 # Force de la relation
    file_path: Optional[str] = None     # Où cette relation existe
    line_number: Optional[int] = None

    # Contexte
    surrounding_tokens: list[str] = field(default_factory=list)
    is_cross_file: bool = False         # Dépendance inter-fichiers


# ---------------------------------------------------------------------------
# Entités structurales (fonctions, classes, modules)
# ---------------------------------------------------------------------------

@dataclass
class FunctionInfo:
    """Fonction/méthode enrichie avec analyse de corpus."""
    # Identité
    name: str
    qualified_name: str                 # Module.Class.name
    signature: str                      # Signature complète

    # Localisation
    file_path: str
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int = 0

    # Sémantique
    semantic_role: Optional[str] = None  # "orchestrator", "transformer", "validator", "accessor"
    semantic_tags: list[str] = field(default_factory=list)

    # Tokens
    tokens: list[Token] = field(default_factory=list)
    syntagmas: list[Syntagma] = field(default_factory=list)

    # Métriques corpus
    token_count: int = 0
    unique_tokens: int = 0
    type_token_ratio: float = 0.0       # TTR = unique / total
    lexical_diversity: float = 0.0      # MTLD ou autre mesure
    semantic_entropy: float = 0.0       # Entropie de Shannon sur les POS

    # Métriques traditionnelles
    cyclomatic_complexity: int = 1
    cognitive_complexity: int = 0
    parameters: list[str] = field(default_factory=list)
    return_type: Optional[str] = None

    # Dépendances
    calls: list[str] = field(default_factory=list)
    called_by: list[str] = field(default_factory=list)
    local_variables: list[str] = field(default_factory=list)

    # Documentation
    docstring: Optional[str] = None
    comment_ratio: float = 0.0          # Lignes commentaires / lignes code

    # Source
    source_code: str = ""

    # Métadonnées
    is_method: bool = False
    parent_class: Optional[str] = None
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False
    is_generator: bool = False
    is_recursive: bool = False

    # Historique (si git)
    first_commit: Optional[str] = None
    last_commit: Optional[str] = None
    commit_count: int = 0
    authors: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Classe/struct enrichie avec analyse de domaine."""
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int

    # Sémantique
    semantic_domain: Optional[str] = None  # "entity", "service", "repository", "dto"
    semantic_tags: list[str] = field(default_factory=list)

    # Héritage
    base_classes: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)
    subclasses: list[str] = field(default_factory=list)

    # Contenu
    methods: list[FunctionInfo] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)
    class_variables: list[str] = field(default_factory=list)

    # Métriques
    method_count: int = 0
    property_count: int = 0
    inheritance_depth: int = 0
    coupling: int = 0                   # Nombre de classes dépendantes
    cohesion: float = 0.0               # LCOM ou mesure sémantique

    # Source
    source_code: str = ""
    docstring: Optional[str] = None


@dataclass
class ModuleInfo:
    """Module/fichier source comme unité de corpus."""
    file_path: str
    file_name: str
    language: str

    # Métadonnées fichier
    size_bytes: int = 0
    sha256: str = ""
    lines_total: int = 0
    lines_code: int = 0
    lines_comments: int = 0
    lines_blank: int = 0

    # Contenu analysé
    tokens: list[Token] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    # Réseau sémantique local
    semantic_nodes: list[SemanticNode] = field(default_factory=list)

    # Métriques corpus
    token_count: int = 0
    unique_tokens: int = 0
    type_token_ratio: float = 0.0
    lexical_diversity: float = 0.0
    semantic_entropy: float = 0.0

    # Métriques traditionnelles
    avg_function_complexity: float = 0.0
    max_function_complexity: int = 0
    external_dependencies: list[str] = field(default_factory=list)
    internal_dependencies: list[str] = field(default_factory=list)

    # Profil stylistique
    identifier_style: Optional[str] = None  # "snake_case", "camelCase", "PascalCase"
    avg_identifier_length: float = 0.0
    comment_density: float = 0.0

    # Résumé
    summary: str = ""

    # Historique
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    first_commit: Optional[str] = None
    last_commit: Optional[str] = None
    authors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Corpus global
# ---------------------------------------------------------------------------

@dataclass
class CorpusIndex:
    """Index global du corpus — équivalent d'un index de corpus linguistique."""
    root_path: str
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Statistiques
    total_files: int = 0
    total_tokens: int = 0
    total_unique_tokens: int = 0
    total_functions: int = 0
    total_classes: int = 0

    # Distribution
    files_by_language: dict[str, int] = field(default_factory=dict)
    tokens_by_language: dict[str, int] = field(default_factory=dict)

    # Vocabulaire
    vocabulary: list[str] = field(default_factory=list)  # Lemmes uniques
    vocabulary_by_pos: dict[str, list[str]] = field(default_factory=dict)

    # Dépendances
    all_external_dependencies: list[str] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)

    # Réseau sémantique global
    semantic_network: dict = field(default_factory=dict)  # Nodes + Edges

    # Métriques globales
    global_type_token_ratio: float = 0.0
    global_entropy: float = 0.0
    mean_semantic_density: float = 0.0

    # Historique
    commit_range: Optional[tuple[str, str]] = None
    time_span_days: Optional[int] = None

    # Rapports
    modules: list[ModuleInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Filiation logicielle — clones, similarité, PDG, familles, architecture
# (Cf. xAnalyse-theorie.txt / xAnalyse-tools.txt)
# ---------------------------------------------------------------------------

class CloneType(Enum):
    """Typologie standard de la détection de clones (Roy & Cordy)."""
    TYPE_I = "I"       # Copie exacte (hors espaces/commentaires)
    TYPE_II = "II"     # Renommage d'identifiants, logique identique
    TYPE_III = "III"   # Ajouts/suppressions mineurs, structure conservée
    TYPE_IV = "IV"     # Même comportement, code différent (sémantique)
    NONE = "none"


class FiliationLevel(Enum):
    """Niveaux de filiation entre deux unités de code (§14 xAnalyse-theorie)."""
    A_COPY = "A"              # Copie directe
    B_FORK = "B"              # Fork : noyau identique, enrichi
    C_REWRITE = "C"           # Réécriture : même architecture, code différent
    D_CONVERGENCE = "D"       # Convergence : indépendants, motif similaire
    UNRELATED = "none"        # Aucun indice suffisant


@dataclass
class CloneMatch:
    """Correspondance de clone entre deux fonctions/méthodes."""
    function_a: str                     # qualified_name
    function_b: str
    file_a: str
    file_b: str
    clone_type: CloneType
    similarity: float                   # score composite [0,1]
    type1_score: float = 0.0            # similarité texte normalisé
    type2_score: float = 0.0            # similarité après alpha-renommage
    type3_score: float = 0.0            # similarité séquence (ratio)
    behavioral_score: float = 0.0       # similarité comportementale (Type IV)
    evidence: list[str] = field(default_factory=list)


@dataclass
class SimilarityReport:
    """Rapport de similarité multi-métrique entre deux fichiers/entités."""
    entity_a: str
    entity_b: str
    levenshtein_ratio: float = 0.0      # sur séquence d'identifiants normalisée
    jaccard_identifiers: float = 0.0    # ensembles de noms (fonctions/classes)
    jaccard_imports: float = 0.0        # ensembles de dépendances
    jaccard_concepts: float = 0.0       # ensembles de lemmes non-stop
    cosine_tokens: float = 0.0          # vecteurs de fréquence de lemmes
    composite_score: float = 0.0        # moyenne pondérée


@dataclass
class DependencyGraphNode:
    """Nœud d'un Program/Code Dependence Graph simplifié (PDG-lite)."""
    id: str
    label: str
    kind: str                           # "stmt", "call", "def", "use", "branch"
    line: int = 0


@dataclass
class DependencyGraphEdgePDG:
    """Arête d'un PDG-lite : dépendance de contrôle ou de données."""
    source: str
    target: str
    kind: str                           # "control" | "data"


@dataclass
class ProgramDependenceGraph:
    """PDG-lite d'une fonction : squelette de contrôle + flux de données."""
    function_qualified_name: str
    nodes: list[DependencyGraphNode] = field(default_factory=list)
    edges: list[DependencyGraphEdgePDG] = field(default_factory=list)

    @property
    def signature_vector(self) -> dict[str, float]:
        """Empreinte structurelle indépendante des noms (pour comparaison)."""
        from collections import Counter
        kinds = Counter(n.kind for n in self.nodes)
        edge_kinds = Counter(e.kind for e in self.edges)
        return {
            "n_nodes": len(self.nodes),
            "n_edges": len(self.edges),
            **{f"node_{k}": v for k, v in kinds.items()},
            **{f"edge_{k}": v for k, v in edge_kinds.items()},
        }


@dataclass
class IdentifierFamily:
    """Famille lexicale d'identifiants apparentés (§9 xAnalyse-theorie)."""
    id: str
    root: str                           # racine lexicale représentative
    members: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    cohesion: float = 0.0               # similarité moyenne intra-famille


@dataclass
class ArchitecturePattern:
    """Motif architectural détecté (état→transformation→évaluation→...)."""
    name: str
    stages: list[str] = field(default_factory=list)
    files_matched: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class FiliationVerdict:
    """Verdict de filiation entre deux fichiers, avec faisceau d'indices."""
    file_a: str
    file_b: str
    level: FiliationLevel
    confidence: float
    evidence: dict[str, float] = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)


@dataclass
class ConcordanceLine:
    """Ligne de concordance — équivalent de l'outil AntConc pour le code.

    Permet de voir un token/lemme dans son contexte (KWIC: Key Word In Context).
    """
    keyword: str
    keyword_pos: SemanticPOS
    left_context: list[str]           # 5 tokens avant
    right_context: list[str]          # 5 tokens après
    file_path: str
    line_number: int
    function_name: Optional[str] = None

    @property
    def context_window(self) -> str:
        left = " ".join(self.left_context)
        right = " ".join(self.right_context)
        return f"{left} [{self.keyword}] {right}"
