# Analyse de filiation logicielle

Ce document relie chaque méthode décrite dans les deux notes théoriques
fournies (`xAnalyse-theorie.txt` — fondements — et `xAnalyse-tools.txt` —
méthodologie appliquée) à son implémentation concrète dans
`src/analyzers/filiation_analyzer.py`. Il complète le README plutôt qu'il
ne le remplace : consultez-le si vous voulez savoir *pourquoi* une commande
calcule ce qu'elle calcule, ou si vous cherchez à ajuster les seuils.

Aucune de ces méthodes n'est probante isolément (§15 et §18 des deux
documents). Le module ne produit jamais une preuve d'auteur, d'antériorité
ou d'intention — seulement des **hypothèses structurelles argumentées**,
fondées sur la convergence d'un faisceau d'indices.

## Correspondance théorie -> implémentation

| Concept théorique | Section source | Implémentation | Commande CLI |
|---|---|---|---|
| Analyse statique multi-niveaux | théorie §1, outils §1 | Tout le pipeline (aucune exécution de code) | — |
| AST / normalisation indépendante de la forme | théorie §2, outils §2-3 | `normalize_type1`, `alpha_rename` | `ccart clones` |
| Détection de clones Type I | théorie §3 | `CloneDetector` (`type1_score`, seuil 0.98) | `ccart clones --min-type I` |
| Détection de clones Type II | théorie §3 | `alpha_rename` + `type2_score` (seuil 0.92) | `ccart clones --min-type II` |
| Détection de clones Type III | théorie §3 | `SequenceMatcher` tolérant sur texte renommé (seuil 0.72) | `ccart clones --min-type III` |
| Détection de clones Type IV | théorie §3 | `behavioral_score` : Jaccard(appels) + rôle + complexité | `ccart clones --min-type IV` |
| Distance de Levenshtein | théorie §4, outils §4 niv.1 | `levenshtein_distance` / `levenshtein_ratio` | `ccart similarity` |
| Similarité de Jaccard | théorie §4, outils §6-7 | `jaccard_similarity` (identifiants, imports, concepts) | `ccart similarity` |
| Similarité cosinus | théorie §4 | `cosine_similarity` sur vecteurs de fréquences lexicales | `ccart similarity` |
| Program Dependence Graph | théorie §5 | `DependencyGraphBuilder` (PDG-lite : contrôle + données) | `ccart pdg` |
| Code Property Graph | théorie §6 | Non implémenté à l'identique (nécessiterait un vrai CFG par langage) ; le PDG-lite en est une approximation volontairement légère | `ccart pdg` |
| Analyse de graphes (centralité, communautés) | théorie §7 | Déjà présent dans `SemanticNetworkAnalyzer` (v2.0) | `ccart network` |
| Motifs / Design & Architectural Patterns | théorie §8, outils §12,§15 | `ArchitecturePatternAnalyzer`, `CANONICAL_PIPELINES` | `ccart architecture` |
| Analyse des identifiants / familles lexicales | théorie §9, outils §6-7 | `IdentifierFamilyAnalyzer` (union-find sur morphèmes + édition) | `ccart identifiers` |
| Fouille de logiciels (Software Repository Mining) | théorie §10 | Partiellement couvert par `DiachronicAnalyzer` (v2.0, nécessite Git) | `ccart stats` |
| Reconstruction de l'évolution | théorie §11, outils §14 | Approché via `size_ratio` et `core_ratio` dans `FiliationClassifier` (proxy sans historique) | `ccart filiation` |
| Réseau conceptuel | théorie §12, outils §16 | `SemanticNetworkAnalyzer.build_cooccurrence_network` (v2.0) | `ccart network` |
| Architecture implicite | théorie §13, outils §15 | `ArchitecturePatternAnalyzer.role_sequence` | `ccart architecture --file <f>` |
| Classification des filiations (Niveaux A-D) | théorie §14, outils §13 | `FiliationClassifier.classify_pair` / `classify_corpus` | `ccart filiation` |
| Limites de l'analyse statique | théorie §15, outils §18 | Rappelée dans les docstrings et l'aide CLI de `ccart filiation` | `ccart filiation --help` |
| Heuristiques combinées | outils §17 | `FiliationClassifier` n'émet un niveau que si plusieurs indices convergent | `ccart filiation` |

## Les quatre niveaux de filiation

`FiliationClassifier.classify_pair` applique les règles suivantes (voir le
code pour les seuils exacts, ajustables) :

- **A — Copie directe** : ratio élevé de clones Type I/II sur le plus petit
  des deux fichiers *et* similarité composite globale élevée.
- **B — Fork** : noyau commun significatif, mais l'un des deux fichiers
  comporte nettement plus de fonctions (enrichissement) et l'architecture
  reste proche.
- **C — Réécriture** : séquence de rôles sémantiques proche (LCS), très peu
  de clones textuels — le squelette architectural a survécu, pas le code.
- **D — Convergence** : motif architectural partiellement partagé mais
  vocabulaire quasi disjoint — deux programmes indépendants ayant répondu
  au même problème de façon similaire, sans emprunt direct.

Si aucun de ces faisceaux ne converge, aucun niveau n'est retenu (niveau
`UNRELATED`, absent des sorties par défaut).

## Portée et limites assumées

- Le PDG-lite (`DependencyGraphBuilder`) est un graphe de contrôle
  séquentiel enrichi d'arêtes def→use détectées par expression régulière :
  ce n'est **pas** un CFG/PDG au sens compilateur (comme Joern ou CodeQL,
  cités en théorie §6). Il sert de *proxy* comparatif, pas de vérité terrain.
- La détection de clones Type IV reste heuristique (comportement approché
  par appels + rôle + complexité), conformément à la remarque de la théorie
  (§3 Type IV : "détection beaucoup plus difficile").
- Comme le rappellent les deux documents sources, ces analyses ne permettent
  de démontrer ni l'auteur, ni l'antériorité exacte, ni l'intention du
  développeur — seulement de construire des hypothèses argumentées.
