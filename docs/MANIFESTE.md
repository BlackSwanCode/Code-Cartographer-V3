# Manifeste Scientifique — CodeCartographer v2.0

## Pourquoi une approche de corpus ?

L'analyse statique de code source a atteint ses limites avec les approches traditionnelles :
- **Métriques isolées** : cyclomatique, lignes de code, couverture — utiles mais déconnectées du sens
- **Graphes de dépendances** : précis techniquement, pauvres sémantiquement
- **Rapports statiques** : inertes, non-queryables, non-explorables

La **linguistique de corpus** offre un cadre scientifique mature pour traiter des collections massives de textes structurés. Transposée au code source, elle permet de :

1. **Traiter le code comme un texte** soumis aux lois de la linguistique
2. **Extraire des patterns implicites** via la statistique (collocations, n-grams)
3. **Mesurer la complexité informationnelle** (entropie, compression)
4. **Identifier des empreintes stylistiques** (stylométrie, authorship)
5. **Suivre l'évolution sémantique** (diachronie, changement de sens)
6. **Modéliser les réseaux de concepts** (sémantique distributionnelle)
7. **Comprendre la dimension sociale** (pragmatique, conventions, genres)

## Analogies fondamentales

| Concept linguistique | Transposition au code | Exemple |
|------------------------|----------------------|---------|
| **Token** | Identifieur, mot-clé, opérateur | `fetch_data`, `import`, `+` |
| **Lemme** | Forme canonique | `fetching` → `fetch` |
| **POS (Part of Speech)** | Rôle sémantique | `VERB` = fonction, `NOUN` = variable |
| **Syntagme** | Séquence sémantique | `fetch_user_data` = [VERB][NOUN][NOUN] |
| **Collocation** | Co-occurrence fréquente | `try` + `except` + `log` |
| **Concordance** | Contexte d'occurrence | KWIC autour de `validate` |
| **Type-Token Ratio** | Diversité lexicale | Lemmes uniques / tokens total |
| **Entropie** | Prédictibilité | Code répétitif vs surprenant |
| **Stylométrie** | Empreinte d'auteur | Préférences de nommage, densité |
| **Diachronie** | Évolution temporelle | Vocabulaire qui change avec le temps |
| **Réseau sémantique** | Graphe de concepts | `User` ↔ `authenticate` ↔ `token` |
| **Pragmatique** | Acte social | TODO/FIXME, conventions d'équipe |

## Méthodologie scientifique

### 1. Annotation
Chaque token reçoit un tag sémantique (POS) adapté au code :
- `VERB` : fonctions, méthodes, actions
- `NOUN` : variables, classes, entités
- `ADJ` : types, qualifiers
- `ADV` : modificateurs (async, decorators)
- `PREP` : imports, dépendances
- `BLOCK` : structures de contrôle

### 2. Lemmatisation
Réduction des formes flexionnelles :
- `fetching`, `fetched`, `fetches` → `fetch`
- `users`, `user_list` → `user`
- Découpage camelCase/snake_case : `DataProcessor` → [data, processor]

### 3. Extraction de patterns
- **N-grams** : séquences récurrentes de n tokens
- **Collocations** : co-occurrences statistiquement significatives (PMI)
- **Syntagmes** : unités sémantiques composées

### 4. Analyse distributionnelle
- **Liste de fréquence** : mots les plus communs
- **Mots-clés** : sur-représentation par log-likelihood
- **Profil lexical** : TTR, MTLD, hapax legomena

### 5. Réseaux
- **Co-occurrence** : concepts liés par contexte partagé
- **Dépendances** : graphe fonctionnel (appels, héritage)
- **Centralité** : concepts clés (PageRank, betweenness)
- **Communautés** : clusters sémantiques (Louvain)

### 6. Entropie
- **Shannon** : diversité des POS dans un fichier
- **Kolmogorov-proxy** : compressibilité = redondance
- **Densité sémantique** : concepts / ligne de code

### 7. Stylométrie
- **MFW** : Most Frequent Words par auteur
- **Delta** : distance entre profils d'usage lexical
- **Complexité lexicale** : MTLD, diversité des identifiants

## Applications

### Recherche académique
- Étude de l'évolution des langages de programmation
- Analyse des pratiques de développement par communauté
- Détection de plagiat et attribution d'auteur
- Compréhension de la dette technique comme changement sémantique

### Industrie
- Cartographie sémantique de codebases legacy
- Détection d'anti-patterns par collocations
- Identification des concepts clés pour refactoring
- Analyse de cohésion d'équipe par profils stylistiques
- Documentation automatique par extraction de réseaux

## Références scientifiques

- Sinclair, J. (1991). *Corpus, Concordance, Collocation*. Oxford University Press.
- McEnery, T. & Wilson, A. (2001). *Corpus Linguistics*. Edinburgh University Press.
- Burrows, J. (2002). "Delta": A measure of stylistic difference. *Literary and Linguistic Computing*.
- Gabrielatos, C. & Marchi, A. (2012). Keyness: Matching metrics to definitions. *Critical Discourse Studies*.
- Gries, S. Th. (2013). *Statistics for Linguistics with R*. De Gruyter.
- Newman, M. (2018). *Networks*. Oxford University Press.
- Shannon, C. (1948). A mathematical theory of communication. *Bell System Technical Journal*.

---

> "Le code source est le dernier grand corpus non exploré par la linguistique."
