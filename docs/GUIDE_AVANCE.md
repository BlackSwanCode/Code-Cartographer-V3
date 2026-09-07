# Guide d'utilisation avancée

## Requêtes SQL directes

Le corpus est stocké dans DuckDB, accessible via SQL :

```python
import duckdb

con = duckdb.connect("corpus.duckdb")

# Fonctions les plus complexes par rôle sémantique
result = con.execute("""
    SELECT semantic_role, 
           AVG(cyclomatic_complexity) as avg_cc,
           COUNT(*) as count
    FROM functions
    GROUP BY semantic_role
    ORDER BY avg_cc DESC
""").fetchall()

# Distribution des POS par fichier
result = con.execute("""
    SELECT file_path, pos, COUNT(*) as freq
    FROM tokens
    GROUP BY file_path, pos
    ORDER BY file_path, freq DESC
""").fetchall()

# Concepts les plus connectés (degré dans le réseau)
result = con.execute("""
    SELECT source_id, COUNT(*) as degree
    FROM dependencies
    GROUP BY source_id
    ORDER BY degree DESC
    LIMIT 20
""").fetchall()
```

## Analyse avec pandas

```python
import duckdb
import pandas as pd

con = duckdb.connect("corpus.duckdb")

# Charger les tokens dans pandas
df = con.execute("SELECT * FROM tokens").fetchdf()

# Analyse par fichier
file_stats = df.groupby('file_path').agg({
    'text': 'count',
    'lemma': 'nunique',
    'pos': lambda x: x.value_counts().to_dict()
}).rename(columns={'text': 'tokens', 'lemma': 'unique_lemmas'})

# Entropie par fichier
from scipy.stats import entropy
file_entropy = df.groupby('file_path')['pos'].apply(
    lambda x: entropy(x.value_counts(normalize=True))
)
```

## Intégration avec NetworkX

```python
from codecartographer import CorpusStore, SemanticNetworkAnalyzer
import networkx as nx

store = CorpusStore("corpus.duckdb")
analyzer = SemanticNetworkAnalyzer(store)

# Construire le réseau
G = analyzer.build_cooccurrence_network(min_weight=2)

# Analyser
communities = analyzer.detect_communities(G)
centrality = analyzer.compute_centrality_metrics(G)

# Visualiser avec matplotlib
import matplotlib.pyplot as plt
pos = nx.spring_layout(G)
nx.draw(G, pos, node_size=[centrality['pagerank'][n]*1000 for n in G.nodes()])
plt.show()
```

## Analyse diachronique avec Git

```python
from codecartographer import DiachronicAnalyzer

analyzer = DiachronicAnalyzer(store, repo_path="/path/to/repo")

# Croissance du vocabulaire
growth = analyzer.compute_vocabulary_growth(time_buckets="month")

# Tendance d'abstraction
trend = analyzer.compute_abstraction_trend()
```

## Export vers d'autres outils

### TXM (logiciel de corpus)
```bash
# Export au format XML-TEI
ccart analyze /repo --output ./corpus --format txm
```

### AntConc
```bash
# Export au format texte brut pour AntConc
ccart analyze /repo --output ./corpus --format txt
```

### Gephi
```bash
# Export du réseau au format GEXF
ccart network --output network.gexf
```

### Tableau / PowerBI
```bash
# Export Parquet pour outils BI
ccart analyze /repo --output ./corpus
# Puis charger les fichiers .parquet dans Tableau
```
