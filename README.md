# CodeCartographer v3.0 🗺️

> **Analyseur de corpus de code source multi-langage**
> 
> *Approche linguistique de corpus appliquée au développement logiciel*

CodeCartographer v3.0 transforme l'analyse statique de code en une discipline scientifique, empruntant ses méthodologies à la **linguistique de corpus**, la **stylométrie** et l'**analyse de discours**.

---

## Philosophie

Le code source n'est pas seulement des instructions pour machines — c'est un **texte naturel structuré**, un acte de communication entre développeurs, soumis aux mêmes lois que les langues naturelles :
- **Vocabulaire** (API, fonctions, variables)
- **Grammaire** (syntaxe, patterns)
- **Style** (conventions, empreintes individuelles)
- **Évolution** (changement sémantique au fil du temps)
- **Pragmatique** (intention, contexte social)

---

## Installation

```bash
pip install codecartographer
# ou avec support LLM local
pip install codecartographer[llm]
```

## Utilisation rapide

### 1. Analyser un dépôt

```bash
ccart analyze /chemin/vers/mon-repo --output ./corpus
```

Construit le corpus dans une base DuckDB avec export Parquet.

### 2. Concordancier (KWIC)

```bash
ccart concordance "fetch_data" --context 5
```

Affiche les occurrences avec contexte (comme AntConc).

### 3. Collocations

```bash
ccart collocations "validate" --window 5
```

Extrait les co-occurrences significatives (PMI).

### 4. N-grams

```bash
ccart ngrams --size 3 --min-freq 3
```

Patterns récurrents de 3 tokens.

### 5. Liste de fréquence

```bash
ccart frequency --pos VERB --lang python
```

Mots les plus fréquents par POS.

### 6. Mots-clés

```bash
ccart keywords python --ref javascript
```

Mots sur-représentés en Python vs JavaScript (log-likelihood).

### 7. Réseau sémantique

```bash
ccart network --output network.html
```

Graphe interactif des concepts (PyVis/D3).

### 8. Entropie

```bash
ccart entropy --file src/main.py
```

Complexité informationnelle.

### 9. Profil stylistique

```bash
ccart profile src/main.py
```

Analyse complète du style.

### 10. Statistiques globales

```bash
ccart stats
```

Vue d'ensemble du corpus.

---

## Filiation logicielle (rétro-ingénierie d'architecture)

Au-delà de la linguistique de corpus, CodeCartographer reconstruit des
hypothèses de **filiation entre programmes** en l'absence d'historique Git —
combinant détection de clones, similarité multi-métrique, PDG simplifié,
familles d'identifiants et motifs architecturaux. Voir [`docs/FILIATION.md`](docs/FILIATION.md)
pour le détail méthodologique complet.

### 11. Détection de clones (Types I à IV)

```bash
ccart clones --min-type II
```

Compare toutes les fonctions du corpus et classe les correspondances :
copie exacte (I), identifiants renommés (II), ajouts/suppressions mineurs
(III), équivalence comportementale (IV).

### 12. Similarité inter-fichiers

```bash
ccart similarity src/a.py src/b.py
# ou, sur tout le corpus:
ccart similarity
```

Levenshtein (identifiants), Jaccard (noms, imports, concepts), cosinus
(fréquences lexicales), agrégés en un score composite.

### 13. Familles d'identifiants

```bash
ccart identifiers --min-similarity 0.6
```

Regroupe les identifiants apparentés (ex : `Genome`, `GlyphDNA`,
`SyntheticGenome`, `OrganismGenome`) même sans préfixe commun explicite.

### 14. Motifs architecturaux

```bash
ccart architecture
ccart architecture --file src/engine.py   # séquence de rôles d'un fichier
```

Détecte des pipelines canoniques (ex : État → Transformation → Évaluation →
Nouvel état) à partir des séquences de rôles sémantiques des fonctions.

### 15. Classification de filiation (A/B/C/D)

```bash
ccart filiation --min-level C --export-json filiation.json
```

Propose, pour chaque paire de fichiers, un niveau de filiation étayé par un
faisceau d'indices :

| Niveau | Nom | Indice dominant |
|--------|-----|------------------|
| **A** | Copie directe | Noyau de fonctions quasi identique (clones Type I/II) |
| **B** | Fork | Noyau commun + enrichissement net de l'un des deux fichiers |
| **C** | Réécriture | Architecture (séquence de rôles) proche, code textuellement différent |
| **D** | Convergence | Motif partiellement partagé, vocabulaire indépendant |

> Comme toute analyse statique, ces verdicts sont des **hypothèses
> argumentées**, jamais des preuves d'auteur, d'antériorité ou d'intention
> (cf. `docs/FILIATION.md`, section Limites).

### 16. PDG-lite d'une fonction

```bash
ccart pdg module.fonction --compare-to autre_module.autre_fonction
```

Affiche le squelette de contrôle/données d'une fonction et, avec
`--compare-to`, une similarité structurelle indépendante des noms
d'identifiants — utile pour repérer des clones Type III/IV.

---

## Architecture

```
SOURCE (multi-langage: Python, JS, TS, C#, Go, Rust, Java, etc.)
    ↓
PARSER (Tree-sitter — grammaires universelles)
    ↓
TOKENIZER (tokenisation sémantique avec POS-tagging)
    ↓
ANNOTATEUR (lemmatisation, détection scope, rôles sémantiques)
    ↓
CORPUS STORE (DuckDB — requêtes SQL analytiques)
    ↓
ANALYSEURS
    ├── Stylométrie (MFW, Delta, profils d'auteurs)
    ├── Réseaux sémantiques (co-occurrence, centralité, communautés)
    ├── Diachronie (évolution vocabulaire, abstraction)
    └── Entropie (Shannon, Kolmogorov-proxy, densité)
    ↓
VISUALISATION (Rich CLI, PyVis, export D3/Parquet)
```

---

## Les 7 piliers de l'analyse

| # | Pilier | Transposition | Outil |
|---|--------|---------------|-------|
| 1 | **Annotation linguistique** | POS-tagging sémantique du code | `VERB`, `NOUN`, `ADJ`, `ADV` |
| 2 | **Stylométrie** | Empreinte stylistique du développeur | MFW, Delta, authorship |
| 3 | **Analyse diachronique** | Évolution temporelle du vocabulaire | Git history, heatmaps |
| 4 | **Collocation** | Patterns récurrents (try-except-log) | PMI, n-grams |
| 5 | **Réseaux sémantiques** | Graphes conceptuels | NetworkX, PyVis |
| 6 | **Entropie** | Complexité informationnelle | Shannon, Kolmogorov-proxy |
| 7 | **Pragmatique** | Code comme acte social | TODO/FIXME, conventions |
| 8 | **Détection de clones** | Filiation textuelle (I-IV) | Levenshtein, alpha-renommage |
| 9 | **PDG-lite** | Filiation structurelle | Graphe contrôle + données |
| 10 | **Motifs architecturaux** | Filiation architecturale | Séquences de rôles, LCS |
| 11 | **Classification A/B/C/D** | Hypothèse de filiation globale | Faisceau d'indices convergents |

---

## Métriques nouvelles

| Métrique | Définition | Interprétation |
|----------|-----------|----------------|
| **Densité sémantique** | Concepts uniques / lignes | Haut = efficace, Bas = verbeux |
| **Entropie syntaxique** | Shannon sur les POS | Haut = imprévisible, Bas = répétitif |
| **Score idiomaticité** | Distance aux patterns canoniques | Haut = idiomatique |
| **Cohésion conceptuelle** | Modularité sémantique | Haut = focusé |
| **Taux d'élaboration** | Ratio commentaires/code | Haut = documenté |
| **Profil stylistique** | Vecteur de fréquences | Empreinte unique par dev |

---

## Formats de sortie

- **DuckDB** : Base analytique locale (requêtes SQL)
- **Parquet** : Export pour pandas/Spark/DuckDB externe
- **HTML** : Réseaux sémantiques interactifs (PyVis)
- **JSON** : API et intégrations
- **CSV** : Analyse dans Excel/R

---

## Langages supportés

| Langage | Extension | Parsing |
|---------|-----------|---------|
| Python | `.py` | Tree-sitter + Regex fallback |
| JavaScript | `.js`, `.mjs`, `.cjs` | Tree-sitter |
| TypeScript | `.ts`, `.tsx` | Tree-sitter |
| C# | `.cs` | Tree-sitter |
| Go | `.go` | Tree-sitter |
| Rust | `.rs` | Tree-sitter |
| Java | `.java` | Tree-sitter |
| C/C++ | `.c`, `.cpp`, `.h` | Tree-sitter |
| PowerShell | `.ps1`, `.psm1` | Regex |
| Ruby | `.rb` | Tree-sitter |
| PHP | `.php` | Tree-sitter |
| Swift | `.swift` | Tree-sitter |
| Kotlin | `.kt` | Tree-sitter |
| Scala | `.scala` | Tree-sitter |

---

## Exemples d'utilisation avancée

### Détection de plagiat / authorship

```python
from codecartographer.analyzers import StylometricAnalyzer

analyzer = StylometricAnalyzer(store)
delta = analyzer.compute_delta_distance("alice", "bob")
# delta < 1 = même auteur probable
```

### Analyse de réseau conceptuel

```python
from codecartographer.analyzers import SemanticNetworkAnalyzer

analyzer = SemanticNetworkAnalyzer(store)
G = analyzer.build_cooccurrence_network()
communities = analyzer.detect_communities(G)
key_concepts = analyzer.find_key_concepts(G, top_n=20)
```

### Requêtes SQL directes sur le corpus

```python
import duckdb

con = duckdb.connect("corpus.duckdb")
result = con.execute("""
    SELECT semantic_role, AVG(cyclomatic_complexity) as avg_cc
    FROM functions
    GROUP BY semantic_role
    ORDER BY avg_cc DESC
""").fetchall()
```

---

## Contribuer

```bash
git clone https://github.com/codecartographer/codecartographer
cd codecartographer
pip install -e ".[dev]"
pytest
```

---

## Licence

MIT — Libre pour la recherche académique et l'industrie.

> *"Le code est le dernier langage naturel structuré qui reste à explorer scientifiquement."*
