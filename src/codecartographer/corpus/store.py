
"""
Stockage et requêtage du corpus de code source.
Utilise DuckDB pour des requêtes analytiques SQL ultra-rapides.
"""

import json
import duckdb
from pathlib import Path
from datetime import datetime
from typing import Optional, Iterator, Any

from ..models import (
    Token, FunctionInfo, ClassInfo, ModuleInfo, CorpusIndex,
    ConcordanceLine, SemanticPOS
)


class CorpusStore:
    """Base de données analytique pour le corpus de code source."""

    def __init__(self, db_path: Optional[str] = None):
        self.conn = duckdb.connect(db_path or ":memory:")
        self._init_schema()

    def _init_schema(self) -> None:
        """Crée le schéma relationnel du corpus."""

            # Ajouter ces lignes AVANT les CREATE TABLE
        self.conn.execute("CREATE SEQUENCE IF NOT EXISTS modules_id_seq")
        self.conn.execute("CREATE SEQUENCE IF NOT EXISTS tokens_id_seq")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY DEFAULT nextval('modules_id_seq'),
                file_path VARCHAR NOT NULL,
                file_name VARCHAR NOT NULL,
                language VARCHAR NOT NULL,
                size_bytes INTEGER,
                sha256 VARCHAR,
                lines_total INTEGER,
                lines_code INTEGER,
                lines_comments INTEGER,
                lines_blank INTEGER,
                token_count INTEGER,
                unique_tokens INTEGER,
                type_token_ratio DOUBLE,
                semantic_entropy DOUBLE,
                avg_function_complexity DOUBLE,
                max_function_complexity INTEGER,
                identifier_style VARCHAR,
                avg_identifier_length DOUBLE,
                external_dependencies JSON,
                internal_dependencies JSON,
                summary VARCHAR,
                analyzed_at TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY DEFAULT nextval('tokens_id_seq'),
                text VARCHAR NOT NULL,
                lemma VARCHAR,
                pos VARCHAR NOT NULL,
                line INTEGER,
                "column" INTEGER,
                scope VARCHAR,
                file_path VARCHAR NOT NULL,
                is_stop BOOLEAN,
                is_external BOOLEAN,
                is_builtin BOOLEAN
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS functions (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                qualified_name VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                start_line INTEGER,
                end_line INTEGER,
                semantic_role VARCHAR,
                token_count INTEGER,
                unique_tokens INTEGER,
                type_token_ratio DOUBLE,
                semantic_entropy DOUBLE,
                cyclomatic_complexity INTEGER,
                parameters JSON,
                return_type VARCHAR,
                calls JSON,
                local_variables JSON,
                docstring VARCHAR,
                comment_ratio DOUBLE,
                source_code VARCHAR,
                is_method BOOLEAN,
                parent_class VARCHAR,
                decorators JSON,
                is_async BOOLEAN
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                qualified_name VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                start_line INTEGER,
                end_line INTEGER,
                semantic_domain VARCHAR,
                base_classes JSON,
                method_count INTEGER,
                inheritance_depth INTEGER,
                coupling INTEGER,
                cohesion DOUBLE
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS syntagmas (
                id INTEGER PRIMARY KEY,
                text VARCHAR NOT NULL,
                pattern_type VARCHAR,
                start_line INTEGER,
                end_line INTEGER,
                file_path VARCHAR NOT NULL,
                semantic_density DOUBLE
            )
        """)

        # -- Filiation logicielle -------------------------------------------------
        # Tables introduites pour la reconstruction de filiation
        # (cf. xAnalyse-theorie.txt / xAnalyse-tools.txt) : clones, similarité
        # inter-fichiers, familles d'identifiants, motifs architecturaux et
        # verdicts de filiation A/B/C/D.

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS function_clones (
                id INTEGER PRIMARY KEY,
                function_a VARCHAR NOT NULL,
                function_b VARCHAR NOT NULL,
                file_a VARCHAR NOT NULL,
                file_b VARCHAR NOT NULL,
                clone_type VARCHAR NOT NULL,
                similarity DOUBLE,
                type1_score DOUBLE,
                type2_score DOUBLE,
                type3_score DOUBLE,
                behavioral_score DOUBLE,
                evidence JSON,
                computed_at TIMESTAMP DEFAULT current_timestamp
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_similarity (
                id INTEGER PRIMARY KEY,
                entity_a VARCHAR NOT NULL,
                entity_b VARCHAR NOT NULL,
                levenshtein_ratio DOUBLE,
                jaccard_identifiers DOUBLE,
                jaccard_imports DOUBLE,
                jaccard_concepts DOUBLE,
                cosine_tokens DOUBLE,
                composite_score DOUBLE,
                computed_at TIMESTAMP DEFAULT current_timestamp
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS identifier_families (
                id VARCHAR PRIMARY KEY,
                root VARCHAR NOT NULL,
                members JSON,
                files JSON,
                cohesion DOUBLE,
                computed_at TIMESTAMP DEFAULT current_timestamp
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS architecture_patterns (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                stages JSON,
                files_matched JSON,
                confidence DOUBLE,
                computed_at TIMESTAMP DEFAULT current_timestamp
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS filiation_verdicts (
                id INTEGER PRIMARY KEY,
                file_a VARCHAR NOT NULL,
                file_b VARCHAR NOT NULL,
                level VARCHAR NOT NULL,
                confidence DOUBLE,
                evidence JSON,
                rationale JSON,
                computed_at TIMESTAMP DEFAULT current_timestamp
            )
        """)

    def insert_module(self, module: ModuleInfo) -> int:
        """Insère un module dans le corpus."""

        ext_deps = json.dumps(module.external_dependencies)
        int_deps = json.dumps(module.internal_dependencies)

        ##

        result = self.conn.execute("""
            INSERT INTO modules (file_path, file_name, language, size_bytes, sha256,
                lines_total, lines_code, lines_comments, lines_blank,
                token_count, unique_tokens, type_token_ratio, semantic_entropy,
                avg_function_complexity, max_function_complexity,
                identifier_style, avg_identifier_length,
                external_dependencies, internal_dependencies, summary, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, [
            module.file_path, module.file_name, module.language,
            module.size_bytes, module.sha256, module.lines_total,
            module.lines_code, module.lines_comments, module.lines_blank,
            module.token_count, module.unique_tokens, module.type_token_ratio,
            module.semantic_entropy, module.avg_function_complexity,
            module.max_function_complexity, module.identifier_style,
            module.avg_identifier_length, ext_deps, int_deps,
            module.summary, module.analyzed_at
        ])

        module_id = result.fetchone()[0]

        ##

        for token in module.tokens:
            self.conn.execute("""
                INSERT INTO tokens (text, lemma, pos, line, "column", scope, file_path, is_stop, is_external, is_builtin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                token.text, token.lemma, token.pos.name, token.line,
                token.column, token.scope.value, token.file_path,
                token.is_stop, token.is_external, token.is_builtin
            ])

        for func in module.functions:
            params = json.dumps(func.parameters)
            calls = json.dumps(func.calls)
            lvars = json.dumps(func.local_variables)
            decors = json.dumps(func.decorators)

            self.conn.execute("""
                INSERT INTO functions (name, qualified_name, file_path, start_line, end_line,
                    semantic_role, token_count, unique_tokens, type_token_ratio, semantic_entropy,
                    cyclomatic_complexity, parameters, return_type, calls, local_variables,
                    docstring, comment_ratio, source_code, is_method, parent_class, decorators, is_async)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                func.name, func.qualified_name, func.file_path, func.start_line, func.end_line,
                func.semantic_role, func.token_count, func.unique_tokens, func.type_token_ratio,
                func.semantic_entropy, func.cyclomatic_complexity, params, func.return_type,
                calls, lvars, func.docstring, func.comment_ratio, func.source_code,
                func.is_method, func.parent_class, decors, func.is_async
            ])

        for cls in module.classes:
            bases = json.dumps(cls.base_classes)

            self.conn.execute("""
                INSERT INTO classes (name, qualified_name, file_path, start_line, end_line,
                    semantic_domain, base_classes, method_count, inheritance_depth, coupling, cohesion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                cls.name, cls.qualified_name, cls.file_path, cls.start_line, cls.end_line,
                cls.semantic_domain, bases, cls.method_count, cls.inheritance_depth,
                cls.coupling, cls.cohesion
            ])

        for func in module.functions:
            for syntagma in func.syntagmas:
                self.conn.execute("""
                    INSERT INTO syntagmas (text, pattern_type, start_line, end_line, file_path, semantic_density)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    syntagma.text, syntagma.pattern_type, syntagma.start_line,
                    syntagma.end_line, func.file_path, syntagma.semantic_density
                ])

        return module_id

    def query_concordance(self, keyword: str, context_size: int = 5,
                         pos_filter: Optional[SemanticPOS] = None,
                         language_filter: Optional[str] = None) -> list[ConcordanceLine]:
        """Requête de concordance (KWIC - Key Word In Context).

        Equivalent de AntConc pour le code source.
        """
        conditions = ["text = ?"]
        params = [keyword]

        if pos_filter:
            conditions.append("pos = ?")
            params.append(pos_filter.name)

        if language_filter:
            conditions.append("file_path LIKE ?")
            params.append(f"%.{language_filter}")

        where_clause = " AND ".join(conditions)

        results = self.conn.execute(f"""
            SELECT text, pos, line, file_path
            FROM tokens
            WHERE {where_clause}
            ORDER BY file_path, line
        """, params).fetchall()

        concordances = []
        for text, pos, line, file_path in results:
            # Récupération du contexte
            left = self.conn.execute("""
                SELECT text FROM tokens 
                WHERE file_path = ? AND line = ? AND id < ?
                ORDER BY id DESC LIMIT ?
            """, [file_path, line, line, context_size]).fetchall()

            right = self.conn.execute("""
                SELECT text FROM tokens 
                WHERE file_path = ? AND line = ? AND id > ?
                ORDER BY id ASC LIMIT ?
            """, [file_path, line, line, context_size]).fetchall()

            concordances.append(ConcordanceLine(
                keyword=keyword,
                keyword_pos=SemanticPOS[pos],
                left_context=[r[0] for r in reversed(left)],
                right_context=[r[0] for r in right],
                file_path=file_path,
                line_number=line
            ))

        return concordances

    def query_collocations(self, word: str, window: int = 5,
                          min_freq: int = 2) -> list[tuple[str, float]]:
        """Extrait les collocations d'un mot (co-occurrences significatives).

        Utilise le PMI (Pointwise Mutual Information) pour mesurer
        la force d'association.
        """
        results = self.conn.execute("""
            WITH target_positions AS (
                SELECT file_path, line, id
                FROM tokens
                WHERE text = ?
            ),
            neighbors AS (
                SELECT t.text, t.lemma, COUNT(*) as freq
                FROM tokens t
                JOIN target_positions tp
                ON t.file_path = tp.file_path
                AND ABS(t.line - tp.line) <= ?
                AND t.text != ?
                GROUP BY t.text, t.lemma
                HAVING COUNT(*) >= ?
            ),
            total_counts AS (
                SELECT COUNT(*) as total FROM tokens
            ),
            word_count AS (
                SELECT COUNT(*) as cnt FROM tokens WHERE text = ?
            )
            SELECT 
                n.text,
                n.freq,
                tc.total,
                wc.cnt,
                LOG2((n.freq * tc.total) / (wc.cnt * (SELECT COUNT(*) FROM tokens WHERE text = n.text))) as pmi
            FROM neighbors n
            CROSS JOIN total_counts tc
            CROSS JOIN word_count wc
            WHERE n.freq >= ?
            ORDER BY pmi DESC
            LIMIT 50
        """, [word, window, word, min_freq, word, min_freq]).fetchall()

        return [(r[0], r[4]) for r in results if r[4] is not None]

    def query_ngrams(self, n: int = 3, min_freq: int = 2,
                     pos_pattern: Optional[list[str]] = None) -> list[tuple[str, int]]:
        """Extrait les n-grams les plus fréquents.

        Args:
            n: Taille des n-grams
            min_freq: Fréquence minimale
            pos_pattern: Pattern de POS à matcher (ex: ["VERB", "NOUN", "NOUN"])
        """
        # Construction dynamique de la requête d'n-grams
        joins = []
        for i in range(1, n):
            joins.append(f"""
                JOIN tokens t{i} 
                ON t{i-1}.file_path = t{i}.file_path 
                AND t{i-1}.line = t{i}.line
                AND t{i}.id = t{i-1}.id + 1
            """)

        select_cols = ", ".join([f"t{i}.text" for i in range(n)])
        group_cols = ", ".join([f"t{i}.text" for i in range(n)])

        pos_conditions = ""
        if pos_pattern:
            pos_conds = [f"t{i}.pos = '{pos_pattern[i]}'" for i in range(n)]
            pos_conditions = "AND " + " AND ".join(pos_conds)

        query = f"""
            SELECT {select_cols}, COUNT(*) as freq
            FROM tokens t0
            {" ".join(joins)}
            WHERE t0.is_stop = FALSE {pos_conditions}
            GROUP BY {group_cols}
            HAVING COUNT(*) >= ?
            ORDER BY freq DESC
            LIMIT 100
        """

        results = self.conn.execute(query, [min_freq]).fetchall()

        return [(" ".join(r[:-1]), r[-1]) for r in results]

    def get_frequency_list(self, by_lemma: bool = True,
                           pos_filter: Optional[str] = None,
                           language_filter: Optional[str] = None) -> list[tuple[str, int]]:
        """Retourne la liste de fréquence (équivalent de la wordlist en corpus).

        Args:
            by_lemma: Grouper par lemme (True) ou forme brute (False)
            pos_filter: Filtrer par POS
            language_filter: Filtrer par langage
        """
        col = "lemma" if by_lemma else "text"
        conditions = ["is_stop = FALSE"]
        params = []

        if pos_filter:
            conditions.append("pos = ?")
            params.append(pos_filter)

        if language_filter:
            conditions.append("file_path LIKE ?")
            params.append(f"%.{language_filter}")

        where_clause = " AND ".join(conditions)

        results = self.conn.execute(f"""
            SELECT {col}, COUNT(*) as freq
            FROM tokens
            WHERE {where_clause}
            GROUP BY {col}
            HAVING {col} IS NOT NULL
            ORDER BY freq DESC
        """, params).fetchall()

        return [(r[0], r[1]) for r in results]

    def get_vocabulary_profile(self, language: Optional[str] = None) -> dict:
        """Profil lexical du corpus (équivalent du vocab profile).

        Retourne:
            - Nombre total de tokens
            - Nombre de types (lemmes uniques)
            - Type-Token Ratio (TTR)
            - Mean Segmental TTR (MSTTR)
            - Hapax legomena (mots n'apparaissant qu'une fois)
        """
        conditions = []
        params = []

        if language:
            conditions.append("file_path LIKE ?")
            params.append(f"%.{language}")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        results = self.conn.execute(f"""
            SELECT 
                COUNT(*) as total_tokens,
                COUNT(DISTINCT lemma) as unique_lemmas,
                COUNT(CASE WHEN freq = 1 THEN 1 END) as hapax_count
            FROM (
                SELECT lemma, COUNT(*) as freq
                FROM tokens
                WHERE is_stop = FALSE AND {where_clause}
                GROUP BY lemma
            )
        """, params).fetchone()

        total_tokens, unique_lemmas, hapax_count = results

        return {
            "total_tokens": total_tokens,
            "unique_lemmas": unique_lemmas,
            "type_token_ratio": unique_lemmas / max(total_tokens, 1),
            "hapax_legomena": hapax_count,
            "hapax_ratio": hapax_count / max(unique_lemmas, 1),
        }

    def get_keyword_analysis(self, target_lang: str,
                            reference_lang: Optional[str] = None) -> list[tuple[str, float]]:
        """Analyse des mots-clés par comparaison avec un corpus de référence.

        Utilise le log-likelihood ratio (G²) pour identifier les mots
        significativement sur-utilisés dans un sous-corpus.

        Args:
            target_lang: Langage cible (ex: "python")
            reference_lang: Langage de référence (ex: "javascript"). 
                          Si None, utilise le reste du corpus.
        """
        # Fréquences dans le corpus cible
        target_freq = self.conn.execute("""
            SELECT lemma, COUNT(*) as freq
            FROM tokens
            WHERE is_stop = FALSE AND file_path LIKE ?
            GROUP BY lemma
        """, [f"%.{target_lang}"]).fetchall()

        target_dict = {r[0]: r[1] for r in target_freq}
        target_total = sum(target_dict.values())

        # Fréquences dans le corpus de référence
        if reference_lang:
            ref_condition = "file_path LIKE ?"
            ref_param = f"%.{reference_lang}"
        else:
            ref_condition = "file_path NOT LIKE ?"
            ref_param = f"%.{target_lang}"

        ref_freq = self.conn.execute(f"""
            SELECT lemma, COUNT(*) as freq
            FROM tokens
            WHERE is_stop = FALSE AND {ref_condition}
            GROUP BY lemma
        """, [ref_param]).fetchall()

        ref_dict = {r[0]: r[1] for r in ref_freq}
        ref_total = sum(ref_dict.values())

        # Calcul du log-likelihood
        import math
        keywords = []

        for word, target_count in target_dict.items():
            ref_count = ref_dict.get(word, 0)

            if target_count < 3:  # Filtrer les très rares
                continue

            # Expected frequencies
            expected_target = target_total * (target_count + ref_count) / (target_total + ref_total)
            expected_ref = ref_total * (target_count + ref_count) / (target_total + ref_total)

            # G² calculation
            g2 = 0
            if target_count > 0 and expected_target > 0:
                g2 += target_count * math.log(target_count / expected_target)
            if ref_count > 0 and expected_ref > 0:
                g2 += ref_count * math.log(ref_count / expected_ref)
            g2 *= 2

            if g2 > 3.84:  # Significatif au seuil p < 0.05
                keywords.append((word, g2))

        keywords.sort(key=lambda x: x[1], reverse=True)
        return keywords[:100]

    # -----------------------------------------------------------------------
    # Filiation logicielle : persistance des résultats
    # -----------------------------------------------------------------------

    def save_clone_matches(self, matches: list) -> None:
        """Persiste les résultats de CloneDetector.detect_all()."""
        self.conn.execute("DELETE FROM function_clones")
        for m in matches:
            self.conn.execute("""
                INSERT INTO function_clones
                    (function_a, function_b, file_a, file_b, clone_type, similarity,
                     type1_score, type2_score, type3_score, behavioral_score, evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                m.function_a, m.function_b, m.file_a, m.file_b, m.clone_type.value,
                m.similarity, m.type1_score, m.type2_score, m.type3_score,
                m.behavioral_score, json.dumps(m.evidence),
            ])

    def save_similarity_reports(self, reports: list) -> None:
        """Persiste les résultats de SimilarityEngine.compare_all_files()."""
        self.conn.execute("DELETE FROM file_similarity")
        for r in reports:
            self.conn.execute("""
                INSERT INTO file_similarity
                    (entity_a, entity_b, levenshtein_ratio, jaccard_identifiers,
                     jaccard_imports, jaccard_concepts, cosine_tokens, composite_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                r.entity_a, r.entity_b, r.levenshtein_ratio, r.jaccard_identifiers,
                r.jaccard_imports, r.jaccard_concepts, r.cosine_tokens, r.composite_score,
            ])

    def save_identifier_families(self, families: list) -> None:
        """Persiste les résultats de IdentifierFamilyAnalyzer.detect_families()."""
        self.conn.execute("DELETE FROM identifier_families")
        for f in families:
            self.conn.execute("""
                INSERT INTO identifier_families (id, root, members, files, cohesion)
                VALUES (?, ?, ?, ?, ?)
            """, [f.id, f.root, json.dumps(f.members), json.dumps(f.files), f.cohesion])

    def save_architecture_patterns(self, patterns: list) -> None:
        """Persiste les résultats de ArchitecturePatternAnalyzer.detect_all()."""
        self.conn.execute("DELETE FROM architecture_patterns")
        for p in patterns:
            self.conn.execute("""
                INSERT INTO architecture_patterns (name, stages, files_matched, confidence)
                VALUES (?, ?, ?, ?)
            """, [p.name, json.dumps(p.stages), json.dumps(p.files_matched), p.confidence])

    def save_filiation_verdicts(self, verdicts: list) -> None:
        """Persiste les résultats de FiliationClassifier.classify_corpus()."""
        self.conn.execute("DELETE FROM filiation_verdicts")
        for v in verdicts:
            self.conn.execute("""
                INSERT INTO filiation_verdicts (file_a, file_b, level, confidence, evidence, rationale)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                v.file_a, v.file_b, v.level.value, v.confidence,
                json.dumps(v.evidence), json.dumps(v.rationale),
            ])

    def export_to_parquet(self, output_dir: Path) -> None:
        """Exporte le corpus au format Parquet pour analyse externe."""
        output_dir.mkdir(parents=True, exist_ok=True)

        tables = [
            "modules", "tokens", "functions", "classes", "syntagmas",
            "function_clones", "file_similarity", "identifier_families",
            "architecture_patterns", "filiation_verdicts",
        ]
        for table in tables:
            self.conn.execute(f"""
                COPY (SELECT * FROM {table})
                TO '{output_dir / f'{table}.parquet'}'
                (FORMAT PARQUET)
            """)

    def close(self) -> None:
        """Ferme la connexion."""
        self.conn.close()
