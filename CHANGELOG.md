# Changelog

## [2.1.0] - Filiation logicielle (rétro-ingénierie d'architecture)

Module ajouté à partir des méthodologies décrites dans `xAnalyse-theorie.txt`
et `xAnalyse-tools.txt` (reconstruction de corpus sans historique Git).

### Ajouté
- **Détection de clones (Types I-IV)** : copie exacte, identifiants renommés,
  ajouts/suppressions mineurs, équivalence comportementale (`src/analyzers/filiation_analyzer.py::CloneDetector`)
- **Métriques de similarité** : distance de Levenshtein, similarité de Jaccard
  (identifiants/imports/concepts), similarité cosinus (vecteurs lexicaux) (`SimilarityEngine`)
- **PDG-lite (Program Dependence Graph simplifié)** : squelette de contrôle +
  flux de données par fonction, comparable indépendamment des noms (`DependencyGraphBuilder`)
- **Familles d'identifiants** : regroupement lexical d'identifiants apparentés
  par morphèmes et distance d'édition (`IdentifierFamilyAnalyzer`)
- **Motifs architecturaux** : détection de pipelines canoniques à partir des
  séquences de rôles sémantiques (`ArchitecturePatternAnalyzer`)
- **Classification de filiation (Niveaux A/B/C/D)** : copie directe, fork,
  réécriture, convergence — avec faisceau d'indices explicite (`FiliationClassifier`)
- **Nouvelles commandes CLI** : `ccart clones`, `ccart similarity`,
  `ccart identifiers`, `ccart architecture`, `ccart filiation`, `ccart pdg`
- **Nouvelles tables DuckDB** : `function_clones`, `file_similarity`,
  `identifier_families`, `architecture_patterns`, `filiation_verdicts`
  (exportées en Parquet comme le reste du corpus)
- **Documentation** : `docs/FILIATION.md` détaille la correspondance entre
  chaque méthode théorique et son implémentation

## [2.0.0] - 2026-05-21

### Ajouté
- **Architecture corpus complète** : passage d'un parseur statique à un système d'analyse de corpus
- **POS-tagging sémantique** : annotation linguistique du code (VERB, NOUN, ADJ, ADV, PREP, etc.)
- **Lemmatisation** : réduction des formes flexionnelles (fetching → fetch)
- **Tokenisation avancée** : découpage camelCase/snake_case en unités sémantiques
- **Corpus Store DuckDB** : base analytique avec requêtes SQL
- **Concordancier** : KWIC (Key Word In Context) comme AntConc
- **Collocations** : extraction par PMI (Pointwise Mutual Information)
- **N-grams** : séquences récurrentes de tokens
- **Liste de fréquence** : wordlist avec TTR et hapax legomena
- **Analyse de mots-clés** : log-likelihood ratio pour sous-corpus
- **Réseaux sémantiques** : co-occurrence, centralité, communautés (Louvain)
- **Stylométrie** : MFW, Delta de Burrows, profils d'auteurs
- **Analyse diachronique** : évolution vocabulaire via Git history
- **Entropie** : Shannon, Kolmogorov-proxy, densité sémantique
- **CLI Rich** : interface en ligne de commande avec tableaux et arbres
- **Export Parquet** : intégration avec pandas/Spark/DuckDB externe
- **Support 20+ langages** : via Tree-sitter et regex fallback
- **Tests unitaires** : pytest avec 95%+ coverage

### Changé
- Parser : AST natif + Regex → Tree-sitter universel
- Stockage : JSON/CSV → DuckDB analytique
- Métriques : complexité cyclomatique → entropie + densité sémantique + TTR
- Architecture : monolithe → modules spécialisés (parsers, corpus, analyzers)

### Supprimé
- Support VB/VBA (temporairement, retour en v2.1)
- Format texte brut (remplacé par Rich CLI)

## [1.0.0] - 2026-05-21

### Ajouté
- Parsing Python via AST natif
- Parsing C#, VB, JS, PowerShell via Regex
- Extraction fonctions, classes, variables, imports
- Complexité cyclomatique
- Graphe de dépendances
- Rapports JSON/CSV/Texte
- SHA-256 des fichiers
- Métriques lignes (code, commentaires, blancs)
