#!/usr/bin/env python3
"""
Corpus Mapper v3.0
Détecte le langage de programmation de fichiers texte et les renomme avec la bonne extension.
Interface CLI avec statistiques et progression "Feng Shui".
Support de l'exploration récursive des sous-dossiers.
"""

import argparse
import re
from pathlib import Path
from collections import Counter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

# --- Configuration des Heuristiques ---
PATTERNS = {
    '.java': [r'public\s+class\s+\w+', r'import\s+java\.', r'public\s+static\s+void\s+main\s*\('],
    '.ps1': [r'#!/usr/bin/env\s+(pwsh|powershell)', r'\b(Get|Set|Invoke|New|Remove)-\w+', r'\$\w+\s*=', r'param\s*\('],
    '.vbs': [r'WScript\.', r'CreateObject\s*\(', r'(?m)^\s*Dim\s+', r'(?m)^\s*Set\s+\w+\s*='],
    '.vba': [r'(?i)Option\s+Explicit', r'(?m)^\s*Sub\s+\w+', r'(?m)^\s*Function\s+\w+', r'(?m)^\s*End\s+Sub'],
    '.rb': [r'#!/usr/bin/env ruby', r'require\s+[\'"]\w+[\'"]', r'(?m)^\s*def\s+\w+', r'\bputs\s+'],
    '.js': [r'#!/usr/bin/env node', r'\b(const|let|var)\s+\w+\s*=', r'require\s*\(', r'module\.exports'],
    '.py': [r'#!/usr/bin/env python', r'import\s+\w+', r'(?m)^\s*def\s+\w+\s*\(', r'print\s*\('],
    '.c': [r'#include\s*<[a-z]+\.h>', r'int\s+main\s*\(', r'void\s*\w+\s*\('],
    '.pl': [r'#!/usr/bin/perl', r'use\s+strict;', r'my\s+\$'],
    '.sh': [r'#!/bin/bash', r'#!/bin/sh', r'chmod\s+\+x'],
    '.php': [r'<\?php', r'\$_(GET|POST|REQUEST|SERVER)', r'\becho\s+'],
    '.html': [r'<!DOCTYPE\s+html', r'<html>', r'<head>', r'<body>'],
    '.xml': [r'<\?xml\s+version=', r'<[a-zA-Z0-9_]+>.*</[a-zA-Z0-9_]+>']
}

def detect_language(content: str) -> str:
    """Retourne l'extension détectée ou '.unknown'."""
    for ext, keywords in PATTERNS.items():
        if any(re.search(kw, content, re.IGNORECASE | re.MULTILINE) for kw in keywords):
            return ext
    return '.unknown'

def collect_files_recursively(directory: Path, extension: str) -> list:
    """Collecte récursivement tous les fichiers avec l'extension donnée."""
    files = []

    # Parcours récursif avec rglob
    for filepath in directory.rglob(f"*{extension}"):
        if filepath.is_file():
            files.append(filepath)

    # Gestion case-insensitive pour les extensions
    # Si l'extension est en minuscules, vérifier aussi en majuscules
    if extension == extension.lower():
        for filepath in directory.rglob(f"*{extension.upper()}"):
            if filepath.is_file():
                files.append(filepath)

    # Supprimer les doublons
    return list(set(files))

def display_tree(directory: Path, files: list, max_items: int = 3) -> Tree:
    """Affiche l'arborescence des fichiers trouvés."""
    tree = Tree(f"📁 [bold cyan]{directory.name}[/bold cyan]")

    # Grouper les fichiers par dossier parent
    files_by_dir = {}
    for filepath in files:
        parent = filepath.parent
        if parent not in files_by_dir:
            files_by_dir[parent] = []
        files_by_dir[parent].append(filepath.name)

    # Construire l'arbre
    for idx, (parent, filenames) in enumerate(sorted(files_by_dir.items())):
        if idx >= max_items and len(files_by_dir) > max_items:
            tree.add(f"[dim]... et {len(files_by_dir) - max_items} autres dossiers[/dim]")
            break

        rel_path = parent.relative_to(directory)
        if str(rel_path) == '.':
            branch = tree.add(f"📄 [green]{len(filenames)} fichier(s)[/green]")
        else:
            branch = tree.add(f"📂 [yellow]{rel_path}[/yellow] [dim]({len(filenames)} fichiers)[/dim]")

        # Afficher quelques noms de fichiers
        for filename in filenames[:3]:
            branch.add(f"└── {filename}")
        if len(filenames) > 3:
            branch.add(f"[dim]└── ... et {len(filenames) - 3} autres[/dim]")

    return tree

def main():
    # --- 1. Configuration CLI ---
    parser = argparse.ArgumentParser(
        description="Détecte le langage de fichiers texte et les renomme avec la bonne extension (recherche récursive).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exemples:\n  python corpus_mapper.py ./PS\n  python corpus_mapper.py ./MonCorpus --dry-run --bytes 4096"
    )
    parser.add_argument("directory", type=str, help="Chemin du répertoire à analyser (ex: ./PS)")
    parser.add_argument("-e", "--ext", default=".txt", help="Extension cible à traiter (défaut: .txt)")
    parser.add_argument("-b", "--bytes", type=int, default=2048, help="Nombre d'octets à lire pour l'analyse (défaut: 2048)")
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation : n'applique aucun renommage")
    parser.add_argument("-r", "--recursive", action="store_true", default=True, help="Parcours récursif (activé par défaut)")
    parser.add_argument("--no-recursive", action="store_true", help="Désactive le parcours récursif")

    args = parser.parse_args()
    console = Console()

    # Gérer la récursivité
    recursive = not args.no_recursive

    # --- 2. Validation ---
    target_dir = Path(args.directory)
    if not target_dir.is_dir():
        console.print(f"[bold red]Erreur : Le répertoire '{target_dir}' n'existe pas.[/bold red]")
        return

    # --- 3. Collection récursive des fichiers ---
    if recursive:
        files_to_process = collect_files_recursively(target_dir, args.ext)
    else:
        files_to_process = list(target_dir.glob(f"*{args.ext}")) + list(target_dir.glob(f"*{args.ext.upper()}"))
        files_to_process = list(set(files_to_process))

    if not files_to_process:
        console.print(f"[yellow]Aucun fichier avec l'extension '{args.ext}' trouvé dans {target_dir}.[/yellow]")
        return

    # --- 4. Interface "Feng Shui" ---
    console.print(Panel.fit(
        f"[bold cyan]Corpus Mapper v3.0 (Récursif)[/bold cyan]\n"
        f"Répertoire : [green]{target_dir.absolute()}[/green]\n"
        f"Fichiers trouvés : [bold]{len(files_to_process)}[/bold] *{args.ext}\n"
        f"Mode : [bold red]SIMULATION (Dry Run)[/bold red]" if args.dry_run else f"Mode : [bold green]ACTIF[/bold green]\n"
        f"Recherche : [{'bold green' if recursive else 'yellow'}]{'Récursive' if recursive else 'Non récursive'}[/{'bold green' if recursive else 'yellow'}]",
        border_style="cyan"
    ))

    # Afficher l'arborescence des fichiers
    tree = display_tree(target_dir, files_to_process)
    console.print(tree)
    console.print("")

    stats = Counter()
    dry_run_actions = []
    file_count = 0

    # --- 5. Boucle de progression ---
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, style="cyan", complete_style="green"),
        TaskProgressColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        expand=True
    ) as progress:

        task = progress.add_task(f"[cyan]Analyse en cours...", total=len(files_to_process))

        for filepath in files_to_process:
            # Afficher le chemin relatif pour plus de clarté
            rel_path = filepath.relative_to(target_dir)
            progress.update(task, description=f"[cyan]Analyse de [white]{rel_path}[/white]")

            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(args.bytes)

                detected_ext = detect_language(content)
                stats[detected_ext] += 1
                file_count += 1

                if detected_ext != '.unknown':
                    new_name = filepath.stem + detected_ext
                    new_filepath = filepath.with_name(new_name)

                    if args.dry_run:
                        dry_run_actions.append(f"[yellow]→[/yellow] {rel_path} [dim]→[/dim] [green]{new_name}[/green]")
                    else:
                        if not new_filepath.exists():
                            filepath.rename(new_filepath)
                        else:
                            stats['.conflict'] += 1

            except Exception as e:
                stats['.error'] += 1
                console.print(f"[red]Erreur sur {rel_path}: {e}[/red]")

            progress.advance(task)

    # --- 6. Statistiques Récapitulatives ---
    console.print("\n[bold]📊 Rapport d'analyse[/bold]")

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Extension détectée", justify="left")
    table.add_column("Nombre de fichiers", justify="right")
    table.add_column("Pourcentage", justify="right")

    total_processed = sum(stats.values())
    # Trier par quantité décroissante
    for ext, count in stats.most_common():
        percentage = (count / total_processed * 100) if total_processed > 0 else 0
        color = "green" if ext != '.unknown' and ext != '.error' and ext != '.conflict' else "yellow" if ext == '.unknown' else "red"
        table.add_row(f"[{color}]{ext}[/{color}]", str(count), f"{percentage:.1f}%")

    console.print(table)

    if args.dry_run and dry_run_actions:
        console.print(f"\n[bold]📝 Actions qui seraient effectuées ({len(dry_run_actions)} au total) :[/bold]")
        # Afficher un échantillon représentatif
        if len(dry_run_actions) <= 10:
            for action in dry_run_actions:
                console.print(action)
        else:
            # Afficher les 5 premiers et 5 derniers
            for action in dry_run_actions[:5]:
                console.print(action)
            console.print(f"[dim]... {len(dry_run_actions) - 10} actions intermédiaires ...[/dim]")
            for action in dry_run_actions[-5:]:
                console.print(action)

        console.print("\n[bold cyan]💡 Astuce :[/bold cyan] Relancez la commande sans [bold]--dry-run[/bold] pour appliquer les changements.")
    else:
        console.print(f"\n[bold green]✅ Traitement terminé avec succès ! ({file_count} fichiers traités)[/bold green]")

    # --- 7. Informations supplémentaires ---
    if recursive:
        console.print(f"\n[dim]📁 Arborescence parcourue : {target_dir.absolute()}[/dim]")
        console.print(f"[dim]📊 Fichiers trouvés dans {len(set(str(p.parent) for p in files_to_process))} dossiers différents[/dim]")

if __name__ == "__main__":
    main()
