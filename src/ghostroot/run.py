from __future__ import annotations

import random
import time
from rich.console import Console
from rich.panel import Panel

from ghostroot.config import load_settings
from ghostroot.tools import (
    add_artifact,
    append_research_log,
    load_artifacts,
    make_id,
)
from ghostroot.agents.speaker import generate_artifact
from ghostroot.agents.researcher import analyze_corpus


def main() -> None:
    console = Console()
    s = load_settings()

    console.print(Panel.fit("[bold]GHOSTROOT[/bold] starting…"))
    console.print(f"[dim]Backend:[/dim] {s.backend}")
    console.print(f"[dim]Ollama bin:[/dim] {getattr(s, 'ollama_bin', 'ollama')}")
    console.print(f"[dim]Model:[/dim] {s.ollama_model}")
    console.print()

    # Step 0: Load corpus
    console.print("[bold]Step 0[/bold] Loading artifact corpus…")
    artifacts = load_artifacts(s.artifacts_path)
    console.print(f"[green]✓[/green] Loaded {len(artifacts)} artifacts from {s.artifacts_path}")
    console.print()

    # Step 1: Pick a branch
    branches = ["branch_a", "branch_b"]
    branch = random.choice(branches)
    console.print(f"[bold]Step 1[/bold] Chosen branch: [cyan]{branch}[/cyan]")
    console.print()

    # Step 2: Speaker generates artifact
    artifact_id = make_id("A")
    console.print(f"[bold]Step 2[/bold] Speaker generating new artifact [dim]{artifact_id}[/dim]…")
    t0 = time.perf_counter()
    artifact = generate_artifact(
        ollama_bin=s.ollama_bin,
        model=s.ollama_model,
        branch=branch,
        artifact_id=artifact_id,
        max_words=s.max_speaker_words,
    )
    dt = time.perf_counter() - t0
    console.print(f"[green]✓[/green] Speaker done in {dt:.2f}s")
    console.print(f"[dim]Artifact text:[/dim] {artifact['text']}")
    console.print()

    # Step 3: Save artifact
    console.print("[bold]Step 3[/bold] Saving artifact…")
    add_artifact(s.artifacts_path, artifact)
    console.print(f"[green]✓[/green] Saved to {s.artifacts_path}")
    console.print()

    # Step 4: Reload corpus
    console.print("[bold]Step 4[/bold] Reloading corpus…")
    artifacts = load_artifacts(s.artifacts_path)
    console.print(f"[green]✓[/green] Corpus now has {len(artifacts)} artifacts")
    console.print()

    # Step 5: Researcher analyzes corpus
    entry_id = make_id("R")
    console.print(f"[bold]Step 5[/bold] Researcher analyzing corpus [dim]{entry_id}[/dim]…")
    t0 = time.perf_counter()
    note = analyze_corpus(
        ollama_bin=s.ollama_bin,
        model=s.ollama_model,
        entry_id=entry_id,
        artifacts=artifacts,
        max_hypotheses=s.max_researcher_hypotheses,
    )
    dt = time.perf_counter() - t0
    console.print(f"[green]✓[/green] Researcher done in {dt:.2f}s")
    console.print()

    # Step 6: Save research note
    console.print("[bold]Step 6[/bold] Saving research note…")
    append_research_log(s.research_log_path, note)
    console.print(f"[green]✓[/green] Saved to {s.research_log_path}")
    console.print()

    # Final output
    console.print(Panel.fit(
        f"[bold]GHOSTROOT[/bold] ran 1 cycle\n"
        f"Backend: {s.backend}\n"
        f"Ollama bin: {s.ollama_bin}\n"
        f"Model: {s.ollama_model}"
    ))

    console.print(Panel.fit(
        f"[bold]New artifact[/bold]\n"
        f"ID: {artifact['id']}\n"
        f"Lang: {artifact['language']}\n"
        f"Text: {artifact['text']}\n"
        f"Context: {artifact['metadata']['context']}"
    ))

    console.print(Panel.fit(
        f"[bold]Research note[/bold]\n"
        f"ID: {note['id']}\n"
        f"Artifacts in corpus: {note['metadata']['artifact_count']}\n\n"
        f"{note['summary']}"
    ))


if __name__ == "__main__":
    main()
