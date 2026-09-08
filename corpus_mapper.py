#!/usr/bin/env python3
"""
Corpus Mapper v2.0
Détecte le langage de programmation de fichiers texte et les renomme avec la bonne extension.
Interface CLI avec statistiques et progression "Feng Shui".
"""

import argparse
import re
from pathlib import Path
from collections import Counter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

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

def main():
    # --- 1. Configuration CLI ---
    parser = argparse.ArgumentParser(
        description="Détecte le langage de fichiers texte et les renomme avec la bonne extension.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exemples:\n  python corpus_mapper.py ./PS\n  python corpus_mapper.py ./MonCorpus --dry-run --bytes 4096"
    )
    parser.add_argument("directory", type=str, help="Chemin du répertoire à analyser (ex: ./PS)")
    parser.add_argument("-e", "--ext", default=".txt", help="Extension cible à traiter (défaut: .txt)")
    parser.add_argument("-b", "--bytes", type=int, default=2048, help="Nombre d'octets à lire pour l'analyse (défaut: 2048)")
    parser.add_argument("--dry-run", action="store_true", help="Mode simulation : n'applique aucun renommage")
    
    args = parser.parse_args()
    console = Console()

    # --- 2. Validation ---
    target_dir = Path(args.directory)
    if not target_dir.is_dir():
        console.print(f"[bold red]Erreur : Le répertoire '{target_dir}' n'existe pas.[/bold red]")
        return

    files_to_process = list(target_dir.glob(f"*{args.ext.lower()}")) + list(target_dir.glob(f"*{args.ext.upper()}"))
    # Supprimer les doublons si le système est case-insensitive
    files_to_process = list(set(files_to_process))
    
    if not files_to_process:
        console.print(f"[yellow]Aucun fichier avec l'extension '{args.ext}' trouvé dans {target_dir}.[/yellow]")
        return

    # --- 3. Interface "Feng Shui" ---
    console.print(Panel.fit(
        f"[bold cyan]Corpus Mapper v2.0[/bold cyan]\n"
        f"Répertoire : [green]{target_dir.absolute()}[/green]\n"
        f"Fichiers à traiter : [bold]{len(files_to_process)}[/bold] *{args.ext}\n"
        f"Mode : [bold red]SIMULATION (Dry Run)[/bold red]" if args.dry_run else f"Mode : [bold green]ACTIF[/bold green]",
        border_style="cyan"
    ))

    stats = Counter()
    dry_run_actions = []

    # --- 4. Boucle de progression ---
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
            progress.update(task, description=f"[cyan]Analyse de [white]{filepath.name}[/white]")
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(args.bytes)
                
                detected_ext = detect_language(content)
                stats[detected_ext] += 1

                if detected_ext != '.unknown':
                    new_name = filepath.stem + detected_ext
                    new_filepath = filepath.with_name(new_name)
                    
                    if args.dry_run:
                        dry_run_actions.append(f"[yellow]→[/yellow] {filepath.name} [dim]sera renommé en[/dim] [green]{new_name}[/green]")
                    else:
                        if not new_filepath.exists():
                            filepath.rename(new_filepath)
                        else:
                            stats['.conflict'] += 1
                            
            except Exception as e:
                stats['.error'] += 1
                console.print(f"[red]Erreur sur {filepath.name}: {e}[/red]")
            
            progress.advance(task)

    # --- 5. Statistiques Récapitulatives ---
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
        console.print("\n[bold]📝 Actions qui seraient effectuées (5 premières) :[/bold]")
        for action in dry_run_actions[:5]:
            console.print(action)
        if len(dry_run_actions) > 5:
            console.print(f"[dim]... et {len(dry_run_actions) - 5} autres.[/dim]")
        console.print("\n[bold cyan]💡 Astuce :[/bold cyan] Relancez la commande sans [bold]--dry-run[/bold] pour appliquer les changements.")
    else:
        console.print(f"\n[bold green]✅ Traitement terminé avec succès ![/bold green]")

if __name__ == "__main__":
    main()