
"""
Interface en ligne de commande pour CodeCartographer v2.0.
Inspirée des outils de corpus linguistiques (AntConc, TXM, etc.)
"""

import json
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.tree import Tree

from ..parsers.tree_sitter_parser import TreeSitterParser
from ..corpus.store import CorpusStore
from ..analyzers.corpus_analyzers import (
    StylometricAnalyzer, SemanticNetworkAnalyzer,
    DiachronicAnalyzer, EntropyAnalyzer
)
from ..analyzers.filiation_analyzer import (
    CloneDetector, SimilarityEngine, IdentifierFamilyAnalyzer,
    ArchitecturePatternAnalyzer, FiliationClassifier, DependencyGraphBuilder,
)
from ..models import SemanticPOS, FiliationLevel, CloneType


app = typer.Typer(
    name="codecartographer",
    help="Analyseur de corpus de code source multi-langage",
    rich_markup_mode="rich",
)
console = Console()


# ---------------------------------------------------------------------------
# Commandes principales
# ---------------------------------------------------------------------------

@app.command()
def analyze(
    root: Path = typer.Argument(..., help="Chemin racine du depot a analyser"),
    output: Path = typer.Option(Path("./codecartographer_output"), "--output", "-o",
                                help="Dossier de sortie"),
    db_path: Optional[str] = typer.Option(None, "--db",
                                          help="Chemin de la base DuckDB (defaut: memoire)"),
    verbose: bool = typer.Option(False, "--verbose", "-v",
                                 help="Mode verbeux"),
    ignore_dirs: List[str] = typer.Option(
        [".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"],
        "--ignore",
        help="Dossiers a ignorer"
    ),
):
    """[bold green]Analyse un depot et construit le corpus.[/bold green]

    C'est la commande principale qui parcourt l'arborescence,
    parse chaque fichier, et stocke les resultats dans une base
    DuckDB pour analyse ulterieure.
    """
    output.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        f"[bold blue]CodeCartographer v2.0[/bold blue]\n"
        f"Analyse de corpus de code source\n"
        f"Racine: [cyan]{root}[/cyan]\n"
        f"Sortie: [cyan]{output}[/cyan]",
        title="Configuration",
        border_style="blue"
    ))

    parser = TreeSitterParser()
    store = CorpusStore(str(output / "corpus.duckdb") if db_path is None else db_path)

    # Decouverte des fichiers
    files = []
    for ext in parser._detect_language.__code__.co_consts:
        if isinstance(ext, str) and ext.startswith("."):
            files.extend(root.rglob(f"*{ext}"))

    # Filtrage
    files = [f for f in files if not any(i in str(f) for i in ignore_dirs)]
    files = sorted(set(files))

    console.print(f"[yellow]{len(files)} fichiers source trouves[/yellow]")

    # Parsing
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyse en cours...", total=len(files))

        for file_path in files:
            try:
                source = file_path.read_text(encoding="utf-8", errors="replace")
                module = parser.parse_file(file_path, source)
                store.insert_module(module)

                if verbose:
                    progress.print(f"  [green]✓[/green] {file_path.relative_to(root)}")

                progress.advance(task)
            except Exception as e:
                progress.print(f"  [red]✗[/red] {file_path.relative_to(root)}: {e}")

    # Export
    store.export_to_parquet(output / "parquet")

    console.print(f"\n[bold green]Analyse terminee![/bold green]")
    console.print(f"Corpus stocke dans: [cyan]{output / 'corpus.duckdb'}[/cyan]")
    console.print(f"Export Parquet: [cyan]{output / 'parquet'}[/cyan]")

    # Statistiques rapides
    stats = store.conn.execute("""
        SELECT 
            COUNT(DISTINCT modules.file_path) as files,
            COUNT(*) as tokens,
            COUNT(DISTINCT lemma) as lemmas,
            COUNT(DISTINCT language) as languages
        FROM tokens
        JOIN modules ON tokens.file_path = modules.file_path
    """).fetchone()

    table = Table(title="Statistiques du corpus")
    table.add_column("Metrique", style="cyan")
    table.add_column("Valeur", style="green")
    table.add_row("Fichiers", str(stats[0]))
    table.add_row("Tokens", str(stats[1]))
    table.add_row("Lemmes uniques", str(stats[2]))
    table.add_row("Langages", str(stats[3]))
    console.print(table)

    store.close()


@app.command()
def concordance(
    keyword: str = typer.Argument(..., help="Mot-cle a rechercher"),
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db",
                            help="Chemin de la base DuckDB"),
    context: int = typer.Option(5, "--context", "-c",
                                help="Taille du contexte (tokens de chaque cote)"),
    pos: Optional[str] = typer.Option(None, "--pos",
                                      help="Filtrer par POS (VERB, NOUN, ADJ, etc.)"),
    language: Optional[str] = typer.Option(None, "--lang", "-l",
                                           help="Filtrer par langage"),
    limit: int = typer.Option(50, "--limit", "-n",
                              help="Nombre maximum de resultats"),
):
    """[bold green]Concordancier (KWIC).[/bold green]

    Affiche les occurrences d'un mot dans leur contexte,
    comme l'outil AntConc en linguistique de corpus.
    """
    store = CorpusStore(str(db))

    pos_filter = SemanticPOS[pos.upper()] if pos else None

    results = store.query_concordance(keyword, context, pos_filter, language)

    if not results:
        console.print(f"[yellow]Aucune occurrence de '{keyword}' trouvee.[/yellow]")
        return

    console.print(f"\n[bold]{len(results)} occurrences de '[cyan]{keyword}[/cyan]'[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Gauche", style="dim", justify="right", no_wrap=True)
    table.add_column("Mot-cle", style="bold cyan", justify="center")
    table.add_column("Droite", style="dim", no_wrap=True)
    table.add_column("Fichier", style="green")
    table.add_column("Ligne", style="yellow", justify="right")

    for line in results[:limit]:
        left = " ".join(line.left_context[-context:])
        right = " ".join(line.right_context[:context])
        table.add_row(
            left,
            line.keyword,
            right,
            Path(line.file_path).name,
            str(line.line_number)
        )

    console.print(table)
    store.close()


@app.command()
def collocations(
    word: str = typer.Argument(..., help="Mot de depart"),
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    window: int = typer.Option(5, "--window", "-w",
                               help="Fenetre de co-occurrence"),
    min_freq: int = typer.Option(2, "--min-freq", "-f",
                                 help="Frequence minimale"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """[bold green]Extraction des collocations.[/bold green]

    Identifie les mots qui co-occurrent significativement
    avec le mot donne (PMI - Pointwise Mutual Information).
    """
    store = CorpusStore(str(db))

    results = store.query_collocations(word, window, min_freq)

    if not results:
        console.print(f"[yellow]Aucune collocation trouvee pour '{word}'.[/yellow]")
        return

    console.print(f"\n[bold]Collocations de '[cyan]{word}[/cyan]'[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Mot", style="cyan")
    table.add_column("PMI", style="green", justify="right")
    table.add_column("Force", style="yellow")

    for colloc, pmi in results[:limit]:
        force = "★★★" if pmi > 5 else "★★" if pmi > 3 else "★"
        table.add_row(colloc, f"{pmi:.2f}", force)

    console.print(table)
    store.close()


@app.command()
def ngrams(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    size: int = typer.Option(3, "--size", "-n", help="Taille des n-grams"),
    min_freq: int = typer.Option(2, "--min-freq", "-f"),
    pos_pattern: Optional[str] = typer.Option(None, "--pos",
                                              help="Pattern POS (ex: VERB NOUN NOUN)"),
    limit: int = typer.Option(30, "--limit", "-l"),
):
    """[bold green]Extraction des n-grams.[/bold green]

    Identifie les sequences recurrentes de tokens,
    equivalent des n-grams en linguistique de corpus.
    """
    store = CorpusStore(str(db))

    pattern = pos_pattern.split() if pos_pattern else None

    results = store.query_ngrams(size, min_freq, pattern)

    if not results:
        console.print("[yellow]Aucun n-gram trouve.[/yellow]")
        return

    console.print(f"\n[bold]{size}-grams les plus frequents[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("N-gram", style="cyan")
    table.add_column("Frequence", style="green", justify="right")

    for ngram, freq in results[:limit]:
        table.add_row(ngram, str(freq))

    console.print(table)
    store.close()


@app.command()
def frequency(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    by_lemma: bool = typer.Option(True, "--lemma/--form", help="Grouper par lemme ou forme"),
    pos: Optional[str] = typer.Option(None, "--pos", help="Filtrer par POS"),
    language: Optional[str] = typer.Option(None, "--lang", "-l"),
    limit: int = typer.Option(50, "--limit", "-n"),
):
    """[bold green]Liste de frequence.[/bold green]

    Affiche les mots les plus frequents dans le corpus,
    equivalent de la wordlist en linguistique de corpus.
    """
    store = CorpusStore(str(db))

    results = store.get_frequency_list(by_lemma, pos, language)

    console.print(f"\n[bold]Liste de frequence[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Rang", style="dim", justify="right")
    table.add_column("Mot" if by_lemma else "Forme", style="cyan")
    table.add_column("Frequence", style="green", justify="right")
    table.add_column("Frequence cumulee", style="yellow", justify="right")

    cumulative = 0
    total = sum(r[1] for r in results)

    for i, (word, freq) in enumerate(results[:limit], 1):
        cumulative += freq
        table.add_row(
            str(i),
            word,
            str(freq),
            f"{cumulative/total*100:.1f}%"
        )

    console.print(table)
    store.close()


@app.command()
def keywords(
    target: str = typer.Argument(..., help="Langage cible (ex: python)"),
    reference: Optional[str] = typer.Option(None, "--ref",
                                            help="Langage de reference (defaut: reste du corpus)"),
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    limit: int = typer.Option(30, "--limit", "-n"),
):
    """[bold green]Analyse des mots-cles.[/bold green]

    Identifie les mots significativement sur-representes
    dans un sous-corpus par rapport a un corpus de reference
    (log-likelihood ratio).
    """
    store = CorpusStore(str(db))

    results = store.get_keyword_analysis(target, reference)

    if not results:
        console.print("[yellow]Aucun mot-cle significatif trouve.[/yellow]")
        return

    ref_text = reference or "reste du corpus"
    console.print(f"\n[bold]Mots-cles de [cyan]{target}[/cyan] vs [cyan]{ref_text}[/cyan][/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Mot", style="cyan")
    table.add_column("G²", style="green", justify="right")
    table.add_column("Significativite", style="yellow")

    for word, g2 in results[:limit]:
        sig = "***" if g2 > 10.83 else "**" if g2 > 6.63 else "*" if g2 > 3.84 else ""
        table.add_row(word, f"{g2:.2f}", sig)

    console.print(table)
    console.print("\n[dim]* p<0.05, ** p<0.01, *** p<0.001[/dim]")
    store.close()


@app.command()
def network(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    output: Path = typer.Option(Path("./network.html"), "--output", "-o"),
    min_weight: float = typer.Option(0.1, "--min-weight", "-w"),
    top_n: int = typer.Option(50, "--top", "-n",
                              help="Nombre de concepts cles a afficher"),
):
    """[bold green]Visualisation du reseau semantique.[/bold green]

    Genere un graphe interactif des concepts et leurs relations.
    """
    try:
        from pyvis.network import Network
    except ImportError:
        console.print("[red]PyVis non installe. Installez avec: pip install pyvis[/red]")
        return

    store = CorpusStore(str(db))
    analyzer = SemanticNetworkAnalyzer(store)

    console.print("[yellow]Construction du reseau...[/yellow]")
    graph = analyzer.build_cooccurrence_network(min_weight=min_weight)

    console.print("[yellow]Calcul des centralites...[/yellow]")
    key_concepts = analyzer.find_key_concepts(graph, top_n)

    # Visualisation PyVis
    net = Network(height="800px", width="100%", bgcolor="#222222", font_color="white")
    net.barnes_hut()

    # Ajout des nœuds
    for concept, score in key_concepts:
        size = 20 + score * 50
        net.add_node(concept, label=concept, size=size, 
                    title=f"Score: {score:.3f}")

    # Ajout des arêtes
    for u, v, data in graph.edges(data=True):
        if u in dict(key_concepts) and v in dict(key_concepts):
            net.add_edge(u, v, value=data.get("weight", 1))

    net.save_graph(str(output))

    console.print(f"[bold green]Reseau sauvegarde:[/bold green] [cyan]{output}[/cyan]")
    console.print(f"Ouvrez ce fichier dans votre navigateur.")

    store.close()


@app.command()
def entropy(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    file: Optional[str] = typer.Option(None, "--file", "-f",
                                       help="Fichier specifique (defaut: corpus entier)"),
):
    """[bold green]Analyse de l'entropie.[/bold green]

    Calcule les metriques d'entropie et de complexite informationnelle.
    """
    store = CorpusStore(str(db))
    analyzer = EntropyAnalyzer(store)

    if file:
        profile = analyzer.compute_information_profile(file)

        console.print(f"\n[bold]Profil informationnel: [cyan]{file}[/cyan][/bold]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metrique", style="cyan")
        table.add_column("Valeur", style="green")
        table.add_column("Interpretation", style="yellow")

        table.add_row(
            "Entropie de Shannon",
            f"{profile['shannon_entropy']:.3f} bits",
            "Haute = diversite, Basse = repetition"
        )
        table.add_row(
            "Proxy Kolmogorov",
            f"{profile['kolmogorov_proxy']:.3f}",
            "Bas = compressible (redondant), Haut = complexe"
        )
        table.add_row(
            "Densite semantique",
            f"{profile['semantic_density']:.3f}",
            "Concepts uniques / ligne de code"
        )

        console.print(table)
    else:
        # Entropie globale
        global_entropy = analyzer.compute_shannon_entropy()

        console.print(f"\n[bold]Entropie globale du corpus[/bold]\n")
        console.print(f"Entropie de Shannon: [green]{global_entropy:.3f} bits[/green]")

        # Entropie par langage
        languages = store.conn.execute("""
            SELECT DISTINCT language FROM modules
        """).fetchall()

        table = Table(title="Entropie par langage")
        table.add_column("Langage", style="cyan")
        table.add_column("Entropie", style="green")
        table.add_column("Interpretation", style="yellow")

        for (lang,) in languages:
            files = store.conn.execute("""
                SELECT file_path FROM modules WHERE language = ?
            """, [lang]).fetchall()

            if files:
                entropies = [analyzer.compute_shannon_entropy(f[0]) for f in files]
                avg_entropy = sum(entropies) / len(entropies)

                interp = "Diversifie" if avg_entropy > 2.5 else "Modere" if avg_entropy > 1.5 else "Repetitif"
                table.add_row(lang, f"{avg_entropy:.3f}", interp)

        console.print(table)

    store.close()


@app.command()
def profile(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    file: str = typer.Argument(..., help="Fichier a profiler"),
):
    """[bold green]Profil stylistique d'un fichier.[/bold green]

    Analyse complete du style, de la complexite et de la semantique.
    """
    store = CorpusStore(str(db))

    module = store.conn.execute("""
        SELECT * FROM modules WHERE file_path = ?
    """, [file]).fetchone()

    if not module:
        console.print(f"[red]Fichier '{file}' non trouve dans le corpus.[/red]")
        return

    console.print(f"\n[bold]Profil: [cyan]{file}[/cyan][/bold]\n")

    # Arbre de profil
    tree = Tree(f"[bold]{module[2]}[/bold] ({module[3]})")

    metrics = tree.add("[bold]Metriques[/bold]")
    metrics.add(f"Lignes: {module[6]} (code: {module[7]}, commentaires: {module[8]})")
    metrics.add(f"Tokens: {module[10]} (uniques: {module[11]})")
    metrics.add(f"TTR: {module[12]:.3f}")
    metrics.add(f"Entropie: {module[13]:.3f}")
    metrics.add(f"Complexite moy: {module[14]:.1f} (max: {module[15]})")

    style = tree.add("[bold]Style[/bold]")
    style.add(f"Convention: {module[16] or 'indetermine'}")
    style.add(f"Longueur moy. identifiants: {module[17]:.1f}")

    deps = tree.add("[bold]Dependances[/bold]")
    ext = json.loads(module[18] or "[]")
    int_deps = json.loads(module[19] or "[]")
    deps.add(f"Externes: {', '.join(ext[:5])}{'...' if len(ext) > 5 else ''}")
    deps.add(f"Internes: {', '.join(int_deps[:5])}{'...' if len(int_deps) > 5 else ''}")

    console.print(tree)
    store.close()


@app.command()
def stats(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
):
    """[bold green]Statistiques globales du corpus.[/bold green]"""
    store = CorpusStore(str(db))

    vocab_profile = store.get_vocabulary_profile()

    console.print(f"\n[bold]Statistiques du corpus[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metrique", style="cyan")
    table.add_column("Valeur", style="green")

    table.add_row("Tokens totaux", str(vocab_profile["total_tokens"]))
    table.add_row("Lemmes uniques", str(vocab_profile["unique_lemmas"]))
    table.add_row("Type-Token Ratio", f"{vocab_profile['type_token_ratio']:.4f}")
    table.add_row("Hapax legomena", str(vocab_profile["hapax_legomena"]))
    table.add_row("Ratio hapax", f"{vocab_profile['hapax_ratio']:.2%}")

    console.print(table)

    # Distribution par langage
    lang_dist = store.conn.execute("""
        SELECT language, COUNT(*) as count
        FROM modules
        GROUP BY language
        ORDER BY count DESC
    """).fetchall()

    console.print(f"\n[bold]Distribution par langage[/bold]")

    table2 = Table()
    table2.add_column("Langage", style="cyan")
    table2.add_column("Fichiers", style="green", justify="right")

    for lang, count in lang_dist:
        table2.add_row(lang, str(count))

    console.print(table2)
    store.close()



# ---------------------------------------------------------------------------
# Commandes de filiation logicielle
# (cf. xAnalyse-theorie.txt / xAnalyse-tools.txt)
# ---------------------------------------------------------------------------

def _level_style(level: FiliationLevel) -> tuple[str, str]:
    """Libellé + couleur Rich pour un niveau de filiation."""
    return {
        FiliationLevel.A_COPY: ("A · Copie directe", "bold red"),
        FiliationLevel.B_FORK: ("B · Fork", "bold yellow"),
        FiliationLevel.C_REWRITE: ("C · Réécriture", "bold cyan"),
        FiliationLevel.D_CONVERGENCE: ("D · Convergence", "bold blue"),
        FiliationLevel.UNRELATED: ("— · Aucune", "dim"),
    }[level]


@app.command()
def clones(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    min_type: str = typer.Option("III", "--min-type",
                                 help="Type de clone minimal a afficher (I, II, III, IV)"),
    exclude_same_file: bool = typer.Option(False, "--exclude-same-file",
                                           help="Ignore les clones internes a un meme fichier"),
    save: bool = typer.Option(True, "--save/--no-save",
                              help="Sauvegarde les resultats dans la base"),
    limit: int = typer.Option(40, "--limit", "-n"),
):
    """[bold green]Detection de clones (Types I a IV).[/bold green]

    Compare toutes les fonctions du corpus deux a deux et classe les
    correspondances selon la typologie standard (copie exacte, identifiants
    renommes, ajouts/suppressions mineurs, equivalence comportementale).
    """
    store = CorpusStore(str(db))
    detector = CloneDetector(store)

    console.print("[yellow]Detection des clones en cours (comparaison par blocs de taille)...[/yellow]")
    matches = detector.detect_all(exclude_same_file=exclude_same_file)

    order = {"I": 4, "II": 3, "III": 2, "IV": 1, "NONE": 0}
    threshold = order.get(min_type.upper(), 2)
    filtered = [m for m in matches if order.get(m.clone_type.value, 0) >= threshold]

    if save:
        store.save_clone_matches(matches)
        console.print(f"[dim]{len(matches)} correspondance(s) sauvegardee(s) dans la base.[/dim]")

    if not filtered:
        console.print(f"[yellow]Aucun clone de type >= {min_type.upper()} detecte.[/yellow]")
        store.close()
        return

    console.print(f"\n[bold]{len(filtered)} clone(s) detecte(s) (type >= {min_type.upper()})[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", justify="center")
    table.add_column("Fonction A", style="cyan")
    table.add_column("Fonction B", style="cyan")
    table.add_column("Similarite", justify="right", style="green")
    table.add_column("Indices", style="dim")

    type_colors = {"I": "red", "II": "yellow", "III": "cyan", "IV": "blue"}

    for m in filtered[:limit]:
        color = type_colors.get(m.clone_type.value, "white")
        table.add_row(
            f"[{color}]{m.clone_type.value}[/{color}]",
            m.function_a, m.function_b,
            f"{m.similarity:.2f}",
            "; ".join(m.evidence[:2]),
        )

    console.print(table)
    console.print("\n[dim]Type I: copie exacte · II: identifiants renommes · "
                  "III: ajouts/suppressions mineurs · IV: equivalence comportementale[/dim]")
    store.close()


@app.command()
def similarity(
    file_a: Optional[str] = typer.Argument(None, help="Premier fichier (optionnel: sinon calcule tout le corpus)"),
    file_b: Optional[str] = typer.Argument(None, help="Second fichier"),
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    save: bool = typer.Option(True, "--save/--no-save"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """[bold green]Similarite inter-fichiers (Levenshtein, Jaccard, cosinus).[/bold green]

    Sans arguments: calcule et classe toutes les paires de fichiers du corpus.
    Avec deux fichiers: affiche le detail des metriques pour cette paire.
    """
    store = CorpusStore(str(db))
    engine = SimilarityEngine(store)

    if file_a and file_b:
        r = engine.compare_files(file_a, file_b)

        console.print(f"\n[bold]Similarite: [cyan]{Path(file_a).name}[/cyan] <-> "
                      f"[cyan]{Path(file_b).name}[/cyan][/bold]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metrique", style="cyan")
        table.add_column("Score", style="green", justify="right")

        table.add_row("Levenshtein (identifiants)", f"{r.levenshtein_ratio:.3f}")
        table.add_row("Jaccard (noms fonctions/classes)", f"{r.jaccard_identifiers:.3f}")
        table.add_row("Jaccard (imports/dependances)", f"{r.jaccard_imports:.3f}")
        table.add_row("Jaccard (concepts/lemmes)", f"{r.jaccard_concepts:.3f}")
        table.add_row("Cosinus (frequences lexicales)", f"{r.cosine_tokens:.3f}")
        table.add_row("[bold]Score composite[/bold]", f"[bold]{r.composite_score:.3f}[/bold]")

        console.print(table)
        store.close()
        return

    console.print("[yellow]Calcul de la similarite sur toutes les paires de fichiers...[/yellow]")
    reports = engine.compare_all_files()

    if save:
        store.save_similarity_reports(reports)
        console.print(f"[dim]{len(reports)} paire(s) sauvegardee(s) dans la base.[/dim]")

    console.print(f"\n[bold]Top {min(limit, len(reports))} paires les plus similaires[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Fichier A", style="cyan")
    table.add_column("Fichier B", style="cyan")
    table.add_column("Composite", justify="right", style="green")
    table.add_column("Identifiants", justify="right")
    table.add_column("Concepts", justify="right")

    for r in reports[:limit]:
        table.add_row(
            Path(r.entity_a).name, Path(r.entity_b).name,
            f"{r.composite_score:.3f}", f"{r.jaccard_identifiers:.2f}", f"{r.jaccard_concepts:.2f}",
        )

    console.print(table)
    store.close()


@app.command()
def identifiers(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    min_similarity: float = typer.Option(0.55, "--min-similarity",
                                         help="Seuil de similarite d'edition pour rattacher deux identifiants"),
    min_size: int = typer.Option(2, "--min-size", help="Taille minimale d'une famille"),
    save: bool = typer.Option(True, "--save/--no-save"),
    limit: int = typer.Option(25, "--limit", "-n"),
):
    """[bold green]Familles lexicales d'identifiants.[/bold green]

    Regroupe les noms de fonctions/classes apparentes (ex: Genome, GlyphDNA,
    SyntheticGenome, OrganismGenome) meme sans prefixe commun explicite.
    """
    store = CorpusStore(str(db))
    analyzer = IdentifierFamilyAnalyzer(store, min_similarity=min_similarity, min_family_size=min_size)

    families = analyzer.detect_families()

    if save:
        store.save_identifier_families(families)

    if not families:
        console.print("[yellow]Aucune famille d'identifiants detectee.[/yellow]")
        store.close()
        return

    console.print(f"\n[bold]{len(families)} famille(s) lexicale(s) detectee(s)[/bold]\n")

    for fam in families[:limit]:
        tree = Tree(f"[bold cyan]{fam.root}[/bold cyan] "
                    f"([green]{len(fam.members)} membres[/green], "
                    f"cohesion={fam.cohesion:.2f})")
        members_branch = tree.add("Identifiants")
        for m in fam.members[:15]:
            members_branch.add(m)
        if len(fam.members) > 15:
            members_branch.add(f"... (+{len(fam.members) - 15})")

        files_branch = tree.add("Fichiers")
        for f in fam.files[:5]:
            files_branch.add(Path(f).name)
        if len(fam.files) > 5:
            files_branch.add(f"... (+{len(fam.files) - 5})")

        console.print(tree)

    store.close()


@app.command()
def architecture(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    file: Optional[str] = typer.Option(None, "--file", "-f",
                                       help="N'affiche que la sequence de roles de ce fichier"),
    save: bool = typer.Option(True, "--save/--no-save"),
):
    """[bold green]Motifs architecturaux (pipelines de roles semantiques).[/bold green]

    Detecte des motifs comme "Etat -> Transformation -> Evaluation -> Nouvel
    etat" a partir de la sequence des roles semantiques des fonctions.
    """
    store = CorpusStore(str(db))
    analyzer = ArchitecturePatternAnalyzer(store)

    if file:
        seq = analyzer.role_sequence(file)
        console.print(f"\n[bold]Sequence architecturale: [cyan]{file}[/cyan][/bold]\n")
        console.print(" -> ".join(seq) if seq else "[dim](aucun role semantique identifie)[/dim]")

        matches = analyzer.match_canonical(file)
        if matches:
            console.print("\n[bold]Motifs canoniques correspondants[/bold]")
            for m in matches:
                console.print(f"  [green]{m.name}[/green] (confiance={m.confidence:.2f}): "
                              f"{' -> '.join(m.stages)}")
        store.close()
        return

    console.print("[yellow]Detection des motifs architecturaux sur le corpus...[/yellow]")
    patterns = analyzer.detect_all()

    if save:
        store.save_architecture_patterns(patterns)

    if not patterns:
        console.print("[yellow]Aucun motif canonique detecte.[/yellow]")
        store.close()
        return

    table = Table(show_header=True, header_style="bold magenta", title="Motifs architecturaux detectes")
    table.add_column("Motif", style="cyan")
    table.add_column("Etapes", style="dim")
    table.add_column("Fichiers", justify="right", style="green")
    table.add_column("Confiance", justify="right")

    for p in patterns:
        table.add_row(p.name, " -> ".join(p.stages), str(len(p.files_matched)), f"{p.confidence:.2f}")

    console.print(table)
    store.close()


@app.command()
def filiation(
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    min_level: str = typer.Option("D", "--min-level",
                                  help="Niveau minimal a afficher (A copie, B fork, C reecriture, D convergence)"),
    save: bool = typer.Option(True, "--save/--no-save"),
    export_json: Optional[Path] = typer.Option(None, "--export-json",
                                               help="Exporte les verdicts detailles en JSON"),
):
    """[bold green]Classification de filiation entre fichiers (Niveaux A/B/C/D).[/bold green]

    Combine detection de clones, similarite lexicale et motifs architecturaux
    pour proposer une hypothese de filiation entre chaque paire de fichiers:

        A - Copie directe : noyau de code quasi identique
        B - Fork          : noyau commun, l'un enrichit l'autre
        C - Reecriture    : meme architecture, code largement different
        D - Convergence   : motif partage, vocabulaire independant

    [dim]Rappel: une analyse statique ne demontre ni l'auteur, ni
    l'anteriorite, ni l'intention -- seulement des hypotheses structurelles
    argumentees (cf. xAnalyse-theorie.txt §15, xAnalyse-tools.txt §18).[/dim]
    """
    store = CorpusStore(str(db))
    classifier = FiliationClassifier(store)

    console.print("[yellow]Analyse de filiation en cours (clones + similarite + architecture)...[/yellow]")
    verdicts = classifier.classify_corpus()

    if save:
        store.save_filiation_verdicts(verdicts)

    order = {"A": 4, "B": 3, "C": 2, "D": 1}
    threshold = order.get(min_level.upper(), 1)
    filtered = [v for v in verdicts if order.get(v.level.value, 0) >= threshold]

    if not filtered:
        console.print(f"[yellow]Aucune filiation de niveau >= {min_level.upper()} detectee.[/yellow]")
        store.close()
        return

    console.print(f"\n[bold]{len(filtered)} relation(s) de filiation (niveau >= {min_level.upper()})[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Fichier A", style="cyan")
    table.add_column("Fichier B", style="cyan")
    table.add_column("Niveau")
    table.add_column("Confiance", justify="right")
    table.add_column("Indice cle", style="dim")

    for v in filtered:
        label, style = _level_style(v.level)
        table.add_row(
            Path(v.file_a).name, Path(v.file_b).name,
            f"[{style}]{label}[/{style}]",
            f"{v.confidence:.2f}",
            v.rationale[0] if v.rationale else "",
        )

    console.print(table)
    console.print("\n[dim]A: copie directe · B: fork · C: reecriture · D: convergence[/dim]")

    if export_json:
        payload = [
            {
                "file_a": v.file_a, "file_b": v.file_b, "level": v.level.value,
                "confidence": v.confidence, "evidence": v.evidence, "rationale": v.rationale,
            }
            for v in filtered
        ]
        export_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[green]Verdicts exportes:[/green] [cyan]{export_json}[/cyan]")

    store.close()


@app.command()
def pdg(
    function: str = typer.Argument(..., help="Nom qualifie de la fonction (ex: module.fonction)"),
    db: Path = typer.Option(Path("./codecartographer_output/corpus.duckdb"), "--db"),
    compare_to: Optional[str] = typer.Option(None, "--compare-to",
                                             help="Nom qualifie d'une seconde fonction a comparer"),
):
    """[bold green]Program Dependence Graph simplifie (PDG-lite) d'une fonction.[/bold green]

    Affiche le squelette de controle et de flux de donnees d'une fonction,
    independamment des noms d'identifiants -- utile pour reperer des clones
    Type III/IV (cf. xAnalyse-theorie.txt §5).
    """
    store = CorpusStore(str(db))
    builder = DependencyGraphBuilder()

    row = store.conn.execute("""
        SELECT qualified_name, source_code FROM functions WHERE qualified_name = ?
    """, [function]).fetchone()

    if not row:
        console.print(f"[red]Fonction '{function}' non trouvee dans le corpus.[/red]")
        store.close()
        return

    pdg_a = builder.build(row[0], row[1] or "")

    tree = Tree(f"[bold]{row[0]}[/bold] ({len(pdg_a.nodes)} noeuds, {len(pdg_a.edges)} arcs)")
    for node in pdg_a.nodes[:30]:
        marker = {"branch": "[yellow]◆[/yellow]", "def": "[green]●[/green]",
                  "call": "[cyan]▶[/cyan]", "stmt": "·"}.get(node.kind, "·")
        tree.add(f"{marker} {node.label}")
    if len(pdg_a.nodes) > 30:
        tree.add(f"... (+{len(pdg_a.nodes) - 30} noeuds)")

    console.print(tree)

    if compare_to:
        row_b = store.conn.execute("""
            SELECT qualified_name, source_code FROM functions WHERE qualified_name = ?
        """, [compare_to]).fetchone()

        if not row_b:
            console.print(f"[red]Fonction '{compare_to}' non trouvee.[/red]")
            store.close()
            return

        pdg_b = builder.build(row_b[0], row_b[1] or "")
        sim = DependencyGraphBuilder.compare(pdg_a, pdg_b)

        console.print(f"\n[bold]Similarite structurelle PDG-lite avec [cyan]{compare_to}[/cyan]: "
                      f"[green]{sim:.3f}[/green][/bold]")
        console.print("[dim]Comparaison independante des noms d'identifiants "
                      "(invariants de structure de graphe).[/dim]")

    store.close()


if __name__ == "__main__":
    app()
