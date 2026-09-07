
"""
Moteurs d'analyse corpus pour le code source.
Implémente les méthodologies de la linguistique de corpus:
- Stylométrie & authorship attribution
- Analyse de réseaux sémantiques
- Analyse diachronique (évolution temporelle)
- Entropie & complexité informationnelle
"""

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional
from datetime import datetime

import networkx as nx
import numpy as np
from scipy import stats

from ..models import (
    Token, FunctionInfo, ModuleInfo, CorpusIndex,
    SemanticNode, DependencyEdge, SemanticPOS
)
from ..corpus.store import CorpusStore


# ---------------------------------------------------------------------------
# 1. STYLOMÉTRIE & AUTHENTICITÉ
# ---------------------------------------------------------------------------

class StylometricAnalyzer:
    """Analyse stylométrique du code source.

    Inspirée des méthodes de stylométrie en linguistique:
    - Most Frequent Words (MFW)
    - Delta de Burrows
    - Mesures de complexité lexicale
    """

    def __init__(self, store: CorpusStore):
        self.store = store

    def compute_author_profile(self, author: str) -> dict:
        """Calcule le profil stylistique d'un auteur.

        Métriques:
        - Longueur moyenne des identifiants
        - Préférence de casse (snake vs camel vs Pascal)
        - Densité de commentaires
        - Vocabulaire préféré (MFW)
        - Complexité moyenne des fonctions
        - Taux d'abstraction (ratio classes/fonctions)
        """
        modules = self.store.conn.execute("""
            SELECT * FROM modules WHERE ? IN (SELECT UNNEST(authors))
        """, [author]).fetchall()

        if not modules:
            return {}

        profile = {
            "author": author,
            "files_analyzed": len(modules),
            "avg_identifier_length": np.mean([m[17] for m in modules if m[17]]),
            "identifier_style_distribution": Counter([m[16] for m in modules if m[16]]),
            "avg_comment_density": np.mean([m[18] for m in modules]),
            "avg_complexity": np.mean([m[14] for m in modules]),
            "total_functions": sum([m[19] for m in modules]),
            "total_classes": sum([m[20] for m in modules]),
        }

        # MFW (Most Frequent Words) de l'auteur
        mfw = self.store.conn.execute("""
            SELECT lemma, COUNT(*) as freq
            FROM tokens
            WHERE file_path IN (
                SELECT file_path FROM modules WHERE ? IN (SELECT UNNEST(authors))
            )
            AND is_stop = FALSE
            GROUP BY lemma
            ORDER BY freq DESC
            LIMIT 50
        """, [author]).fetchall()

        profile["most_frequent_words"] = [(r[0], r[1]) for r in mfw]

        return profile

    def compute_delta_distance(self, author1: str, author2: str,
                              n_mfw: int = 50) -> float:
        """Calcule la distance Delta de Burrows entre deux auteurs.

        La distance Delta est une mesure classique en stylométrie
        pour comparer des profils d'usage lexical.
        """
        # Récupération des MFW combinés
        all_mfw = self.store.conn.execute("""
            SELECT lemma, COUNT(*) as freq
            FROM tokens
            WHERE is_stop = FALSE
            GROUP BY lemma
            ORDER BY freq DESC
            LIMIT ?
        """, [n_mfw]).fetchall()

        mfw_list = [r[0] for r in all_mfw]

        # Fréquences normalisées pour chaque auteur
        def get_freq_vector(author: str) -> list[float]:
            freqs = self.store.conn.execute("""
                SELECT lemma, 
                    CAST(COUNT(*) AS DOUBLE) / (
                        SELECT COUNT(*) FROM tokens 
                        WHERE file_path IN (
                            SELECT file_path FROM modules 
                            WHERE ? IN (SELECT UNNEST(authors))
                        )
                    ) as rel_freq
                FROM tokens
                WHERE file_path IN (
                    SELECT file_path FROM modules WHERE ? IN (SELECT UNNEST(authors))
                )
                AND lemma IN (SELECT UNNEST(?))
                AND is_stop = FALSE
                GROUP BY lemma
            """, [author, author, mfw_list]).fetchall()

            freq_dict = {r[0]: r[1] for r in freqs}
            return [freq_dict.get(w, 0) for w in mfw_list]

        vec1 = get_freq_vector(author1)
        vec2 = get_freq_vector(author2)

        # Calcul du z-score pour chaque vecteur
        def zscore(vec: list[float]) -> list[float]:
            mean = np.mean(vec)
            std = np.std(vec)
            if std == 0:
                return [0] * len(vec)
            return [(v - mean) / std for v in vec]

        z1 = zscore(vec1)
        z2 = zscore(vec2)

        # Distance Delta (Manhattan distance entre z-scores)
        delta = sum(abs(a - b) for a, b in zip(z1, z2)) / len(z1)

        return delta

    def compute_lexical_complexity(self, file_path: str) -> dict:
        """Mesures de complexité lexicale d'un fichier.

        - TTR (Type-Token Ratio)
        - MTLD (Measure of Textual Lexical Diversity)
        - HD-D (Hypergeometric Distribution D)
        """
        tokens = self.store.conn.execute("""
            SELECT lemma FROM tokens 
            WHERE file_path = ? AND is_stop = FALSE
            ORDER BY id
        """, [file_path]).fetchall()

        lemmas = [r[0] for r in tokens if r[0]]

        if not lemmas:
            return {}

        # TTR classique
        ttr = len(set(lemmas)) / len(lemmas)

        # MTLD (Measure of Textual Lexical Diversity)
        mtld = self._compute_mtld(lemmas)

        return {
            "file_path": file_path,
            "total_tokens": len(lemmas),
            "unique_types": len(set(lemmas)),
            "ttr": ttr,
            "mtld": mtld,
        }

    def _compute_mtld(self, tokens: list[str], factor_size: float = 0.72) -> float:
        """Calcule le MTLD (Measure of Textual Lexical Diversity).

        Le MTLD mesure la longueur moyenne des segments où le TTR
        reste constant autour d'une valeur cible (0.72 par défaut).
        """
        def _get_factors(tokens: list[str], factor_size: float) -> list[int]:
            factors = []
            current_types = set()
            current_tokens = 0

            for token in tokens:
                current_types.add(token)
                current_tokens += 1

                ttr = len(current_types) / current_tokens
                if abs(ttr - factor_size) < 0.05:  # Seuil de convergence
                    factors.append(current_tokens)
                    current_types = set()
                    current_tokens = 0

            return factors

        factors_forward = _get_factors(tokens, factor_size)
        factors_backward = _get_factors(list(reversed(tokens)), factor_size)

        all_factors = factors_forward + factors_backward

        if not all_factors:
            return len(tokens)  # Fallback

        return len(tokens) / len(all_factors)


# ---------------------------------------------------------------------------
# 2. RÉSEAUX SÉMANTIQUES
# ---------------------------------------------------------------------------

class SemanticNetworkAnalyzer:
    """Analyse des réseaux sémantiques dans le code source.

    Construit et analyse des graphes de co-occurrence et de dépendance
    entre concepts du codebase.
    """

    def __init__(self, store: CorpusStore):
        self.store = store
        self.graph = nx.DiGraph()

    def build_cooccurrence_network(self, window: int = 5,
                                    min_weight: float = 0.1) -> nx.Graph:
        """Construit un réseau de co-occurrence sémantique.

        Deux concepts sont liés s'ils apparaissent fréquemment
        dans une fenêtre de contexte.
        """
        # Récupération des tokens par fichier
        files = self.store.conn.execute("""
            SELECT DISTINCT file_path FROM tokens WHERE is_stop = FALSE
        """).fetchall()

        cooccurrence = defaultdict(lambda: defaultdict(int))

        for (file_path,) in files:
            tokens = self.store.conn.execute("""
                SELECT lemma, pos, line
                FROM tokens
                WHERE file_path = ? AND is_stop = FALSE AND lemma IS NOT NULL
                ORDER BY line
            """, [file_path]).fetchall()

            # Fenêtre glissante
            for i in range(len(tokens)):
                for j in range(i + 1, min(i + window + 1, len(tokens))):
                    if tokens[i][0] != tokens[j][0]:  # Pas d'auto-cohérence
                        pair = tuple(sorted([tokens[i][0], tokens[j][0]]))
                        cooccurrence[pair[0]][pair[1]] += 1

        # Construction du graphe
        G = nx.Graph()

        for w1, neighbors in cooccurrence.items():
            for w2, weight in neighbors.items():
                if weight >= min_weight:
                    G.add_edge(w1, w2, weight=weight)

        self.graph = G
        return G

    def build_dependency_network(self) -> nx.DiGraph:
        """Construit un réseau de dépendances fonctionnelles.

        Nœuds: fonctions/classes
        Arêtes: appels, héritages, utilisations
        """
        G = nx.DiGraph()

        # Ajout des fonctions comme nœuds
        functions = self.store.conn.execute("""
            SELECT name, qualified_name, file_path, semantic_role, cyclomatic_complexity
            FROM functions
        """).fetchall()

        for name, qname, fpath, role, cc in functions:
            G.add_node(qname, 
                      name=name, 
                      file=fpath, 
                      role=role, 
                      complexity=cc)

        # Ajout des arêtes (appels)
        for name, qname, fpath, role, cc in functions:
            calls = self.store.conn.execute("""
                SELECT UNNEST(calls) FROM functions WHERE qualified_name = ?
            """, [qname]).fetchall()

            for (called,) in calls:
                # Résolution du nom appelé
                target = self.store.conn.execute("""
                    SELECT qualified_name FROM functions 
                    WHERE name = ? AND file_path = ?
                """, [called, fpath]).fetchone()

                if target:
                    G.add_edge(qname, target[0], type="call")

        return G

    def compute_centrality_metrics(self, graph: nx.Graph) -> dict:
        """Calcule les métriques de centralité du réseau.

        - Degree centrality (connectivité locale)
        - Betweenness centrality (ponts entre communautés)
        - Eigenvector centrality (influence globale)
        - PageRank (importance pondérée)
        """
        return {
            "degree": nx.degree_centrality(graph),
            "betweenness": nx.betweenness_centrality(graph, weight="weight"),
            "eigenvector": nx.eigenvector_centrality(graph, weight="weight", max_iter=1000),
            "pagerank": nx.pagerank(graph, weight="weight"),
            "clustering": nx.clustering(graph),
        }

    def detect_communities(self, graph: nx.Graph) -> list[set]:
        """Détecte les communautés sémantiques (clusters de concepts).

        Utilise l'algorithme de Louvain pour la détection de communautés.
        """
        try:
            import community as community_louvain
            partition = community_louvain.best_partition(graph)

            communities = defaultdict(set)
            for node, comm_id in partition.items():
                communities[comm_id].add(node)

            return list(communities.values())
        except ImportError:
            # Fallback: connected components
            return list(nx.connected_components(graph))

    def find_key_concepts(self, graph: nx.Graph, top_n: int = 20) -> list[tuple[str, float]]:
        """Identifie les concepts clés (hubs sémantiques).

        Combine plusieurs métriques de centralité.
        """
        centrality = self.compute_centrality_metrics(graph)

        # Score composite
        scores = {}
        for node in graph.nodes():
            scores[node] = (
                centrality["degree"].get(node, 0) * 0.3 +
                centrality["betweenness"].get(node, 0) * 0.3 +
                centrality["eigenvector"].get(node, 0) * 0.2 +
                centrality["pagerank"].get(node, 0) * 0.2
            )

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]


# ---------------------------------------------------------------------------
# 3. ANALYSE DIACHRONIQUE
# ---------------------------------------------------------------------------

class DiachronicAnalyzer:
    """Analyse de l'évolution temporelle du corpus.

    Utilise l'historique Git pour étudier:
    - Évolution du vocabulaire
    - Grammaticalisation (abstraction croissante)
    - Changement sémantique
    """

    def __init__(self, store: CorpusStore, repo_path: Optional[Path] = None):
        self.store = store
        self.repo_path = repo_path

    def compute_vocabulary_growth(self, time_buckets: str = "month") -> list[dict]:
        """Calcule la croissance du vocabulaire au fil du temps.

        Retourne pour chaque période:
        - Nombre de nouveaux lemmes
        - Nombre de lemmes disparus
        - TTR de la période
        """
        if not self.repo_path:
            return []

        try:
            import git
            repo = git.Repo(self.repo_path)

            commits = list(repo.iter_commits())

            growth_data = []
            seen_lemmas = set()

            for commit in commits[::10]:  # Échantillonnage
                commit_date = datetime.fromtimestamp(commit.committed_date)

                # Récupération du vocabulaire à ce commit
                # (Simplification: on utilise les données actuelles avec filtre temporel)

                new_lemmas = self.store.conn.execute("""
                    SELECT COUNT(DISTINCT lemma)
                    FROM tokens
                    WHERE lemma NOT IN (SELECT UNNEST(?))
                """, [list(seen_lemmas)]).fetchone()[0]

                growth_data.append({
                    "date": commit_date.isoformat(),
                    "new_lemmas": new_lemmas,
                    "cumulative_vocab": len(seen_lemmas) + new_lemmas,
                })

                # Mise à jour
                current = self.store.conn.execute("""
                    SELECT DISTINCT lemma FROM tokens
                """).fetchall()
                seen_lemmas.update(r[0] for r in current if r[0])

            return growth_data

        except ImportError:
            return []

    def compute_abstraction_trend(self) -> dict:
        """Mesure la tendance à l'abstraction (grammaticalisation).

        Ratio classes/fonctions au fil du temps.
        Augmentation = plus d'abstraction (OO)
        Diminution = plus de procédural
        """
        modules = self.store.conn.execute("""
            SELECT language, 
                COUNT(*) as file_count,
                SUM(CASE WHEN semantic_domain = 'entity' THEN 1 ELSE 0 END) as entity_count,
                SUM(CASE WHEN semantic_domain = 'service' THEN 1 ELSE 0 END) as service_count
            FROM classes
            GROUP BY language
        """).fetchall()

        return {
            lang: {
                "abstraction_ratio": (entity + service) / max(files, 1),
                "entity_count": entity,
                "service_count": service,
            }
            for lang, files, entity, service in modules
        }

    def detect_semantic_shift(self, word: str,
                               early_period: tuple[str, str],
                               late_period: tuple[str, str]) -> dict:
        """Détecte le changement sémantique d'un mot entre deux périodes.

        Compare les collocations d'un mot dans deux périodes différentes
        pour identifier les dérives de sens.
        """
        # TODO: Implémentation avec filtre temporel
        return {
            "word": word,
            "early_collocates": [],
            "late_collocates": [],
            "shift_detected": False,
        }


# ---------------------------------------------------------------------------
# 4. ENTROPIE & COMPLEXITÉ INFORMATIONNELLE
# ---------------------------------------------------------------------------

class EntropyAnalyzer:
    """Analyse de l'entropie et de la complexité informationnelle.

    Mesures:
    - Entropie de Shannon (prédicibilité)
    - Entropie conditionnelle (dépendances)
    - Complexité de Kolmogorov (proxy par compression)
    """

    def __init__(self, store: CorpusStore):
        self.store = store

    def compute_shannon_entropy(self, file_path: Optional[str] = None,
                                 by_pos: bool = False) -> float:
        """Calcule l'entropie de Shannon du corpus ou d'un fichier.

        H(X) = -Σ p(x) log₂ p(x)

        Haute entropie = code imprévisible (diversité)
        Basse entropie = code répétitif (patterns)
        """
        if file_path:
            tokens = self.store.conn.execute("""
                SELECT pos, COUNT(*) as freq
                FROM tokens
                WHERE file_path = ?
                GROUP BY pos
            """, [file_path]).fetchall()
        else:
            tokens = self.store.conn.execute("""
                SELECT pos, COUNT(*) as freq
                FROM tokens
                GROUP BY pos
            """).fetchall()

        total = sum(r[1] for r in tokens)

        if total == 0:
            return 0.0

        entropy = -sum(
            (freq / total) * math.log2(freq / total)
            for _, freq in tokens
        )

        return entropy

    def compute_conditional_entropy(self, given_pos: SemanticPOS,
                                     target_pos: SemanticPOS) -> float:
        """Calcule l'entropie conditionnelle H(Target | Given).

        Mesure la prédictibilité d'un POS sachant un autre.
        """
        # P(target | given) = count(given, target) / count(given)
        joint = self.store.conn.execute("""
            SELECT COUNT(*) 
            FROM tokens t1
            JOIN tokens t2 ON t1.file_path = t2.file_path AND t2.id = t1.id + 1
            WHERE t1.pos = ? AND t2.pos = ?
        """, [given_pos.name, target_pos.name]).fetchone()[0]

        given_total = self.store.conn.execute("""
            SELECT COUNT(*) FROM tokens WHERE pos = ?
        """, [given_pos.name]).fetchone()[0]

        if given_total == 0:
            return 0.0

        p_cond = joint / given_total

        if p_cond == 0:
            return 0.0

        return -p_cond * math.log2(p_cond)

    def compute_kolmogorov_proxy(self, file_path: str) -> float:
        """Proxy de la complexité de Kolmogorov par compression.

        K(x) ≈ len(compress(x))

        Plus le code est compressible, plus il est redondant/régulier.
        """
        import zlib

        source = self.store.conn.execute("""
            SELECT source_code FROM functions 
            WHERE file_path = ?
        """, [file_path]).fetchall()

        if not source:
            return 0.0

        combined = "\\n".join(r[0] for r in source if r[0])

        original_size = len(combined.encode('utf-8'))
        compressed = zlib.compress(combined.encode('utf-8'), level=9)
        compressed_size = len(compressed)

        # Ratio de compression
        return compressed_size / original_size if original_size > 0 else 0.0

    def compute_semantic_density(self, file_path: str) -> float:
        """Densité conceptuelle: concepts uniques / lignes de code.

        Mesure l'efficacité sémantique du code.
        """
        result = self.store.conn.execute("""
            SELECT 
                COUNT(DISTINCT lemma) as concepts,
                MAX(line) as lines
            FROM tokens
            WHERE file_path = ? AND is_stop = FALSE
        """, [file_path]).fetchone()

        concepts, lines = result

        return concepts / max(lines, 1) if concepts else 0.0

    def compute_information_profile(self, file_path: str) -> dict:
        """Profil informationnel complet d'un fichier."""
        return {
            "shannon_entropy": self.compute_shannon_entropy(file_path),
            "kolmogorov_proxy": self.compute_kolmogorov_proxy(file_path),
            "semantic_density": self.compute_semantic_density(file_path),
            "max_possible_entropy": math.log2(
                self.store.conn.execute("""
                    SELECT COUNT(DISTINCT pos) FROM tokens WHERE file_path = ?
                """, [file_path]).fetchone()[0] or 1
            ),
        }
