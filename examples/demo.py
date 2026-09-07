#!/usr/bin/env python3
"""
Script de démonstration de CodeCartographer v2.0.
Montre l'utilisation de l'API Python pour l'analyse de corpus.
"""

from pathlib import Path
from codecartographer import (
    TreeSitterParser, CorpusStore,
    StylometricAnalyzer, SemanticNetworkAnalyzer, EntropyAnalyzer
)

# Configuration
REPO_PATH = Path("./test_repo")
OUTPUT_PATH = Path("./demo_output")

print("=" * 60)
print("CodeCartographer v2.0 — Démonstration")
print("=" * 60)

# Étape 1: Parsing
print("\n[1] Parsing des fichiers source...")
parser = TreeSitterParser()

# Exemple avec le fichier main.py du rapport original
sample_python = 