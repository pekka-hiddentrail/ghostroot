from __future__ import annotations

import argparse
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.status import Status


from ghostroot.config import load_settings
from ghostroot.tools import (
    add_artifact,
    append_research_log,
    append_research_question,
    load_artifacts,
    load_research_questions,
    make_id,
    update_artifact_glosses,
    update_research_questions,
)
from ghostroot.agents.speaker import generate_artifact
from ghostroot.agents.researcher import analyze_corpus
from ghostroot.agents.context_researcher import analyze_contextual_fit


def run_speaker_only(count: int) -> None:
    """Run only the speaker agent to generate artifacts."""
    console = Console()
    s = load_settings()

    console.print(Panel.fit(f"[bold]GHOSTROOT[/bold] Speaker-only mode ({count} runs)"))
    console.print(f"[dim]Speaker model:[/dim] {s.ollama_speaker_model}")
    console.print()

    language = "ghostlang"
    total_artifacts = 0

    for run in range(1, count + 1):
        console.print(f"[bold cyan]Run {run}/{count}[/bold cyan]")
        
        artifact_id = make_id("A")
        
        console.print(f"  ID: {artifact_id}")
        
        with console.status(
            "  [dim]Generating...[/dim]",
            spinner="dots",
        ):
            new_artifacts = generate_artifact(
                ollama_bin=s.ollama_bin,
                model=s.ollama_speaker_model,
                branch=language,
                artifact_id=artifact_id,
                max_words=s.max_speaker_words,
            )
        
        # Save artifacts
        for art in new_artifacts:
            add_artifact(s.artifacts_path, art)
            console.print(f"  [green]✓[/green] {art['type']}: {art['text']}")
            total_artifacts += 1
        
        console.print()
    
    console.print(Panel.fit(
        f"[bold green]Complete![/bold green]\n"
        f"Generated {total_artifacts} artifacts across {count} runs\n"
        f"Saved to: {s.artifacts_path}"
    ))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GHOSTROOT: Historical linguistics simulation"
    )
    parser.add_argument(
        "-s", "--speaker",
        type=int,
        metavar="COUNT",
        help="Run only the speaker agent COUNT times (for data generation)"
    )
    
    args = parser.parse_args()
    
    # Speaker-only mode
    if args.speaker:
        if args.speaker < 1:
            print("Error: Speaker count must be >= 1", file=sys.stderr)
            sys.exit(1)
        run_speaker_only(args.speaker)
        return
    
    # Normal full cycle mode
    console = Console()
    s = load_settings()

    console.print(Panel.fit("[bold]GHOSTROOT[/bold] starting…"))
    console.print(f"[dim]Backend:[/dim] {s.backend}")
    console.print(f"[dim]Ollama bin:[/dim] {getattr(s, 'ollama_bin', 'ollama')}")
    console.print(f"[dim]Speaker model:[/dim] {s.ollama_speaker_model}")
    console.print(f"[dim]Researcher model:[/dim] {s.ollama_researcher_model}")
    console.print()

    # Step 0: Load corpus
    console.print("[bold]Step 0[/bold] Loading artifact corpus…")
    artifacts = load_artifacts(s.artifacts_path)
    console.print(f"[green]✓[/green] Loaded {len(artifacts)} artifacts from {s.artifacts_path}")
    console.print()

    # Step 1: Speaker generates artifact
    language = "ghostlang"
    artifact_id = make_id("A")
    console.print(f"[bold]Step 1[/bold] Speaker generating new artifact [dim]{artifact_id}[/dim]…")
    t0 = time.perf_counter()
    with console.status(
        "[bold cyan]Speaker agent is generating an inscription…[/bold cyan]",
        spinner="dots",
    ):
        new_artifacts = generate_artifact(
            ollama_bin=s.ollama_bin,
            model=s.ollama_speaker_model,
            branch=language,
            artifact_id=artifact_id,
            max_words=s.max_speaker_words,
    )
    dt = time.perf_counter() - t0
    console.print(f"[green]✓[/green] Speaker done in {dt:.2f}s")
    for art in new_artifacts:
        console.print(f"[dim]{art['type']}:[/dim] {art['text']}")
    console.print()

    # Step 2: Save artifacts
    console.print(f"[bold]Step 2[/bold] Saving {len(new_artifacts)} artifact(s)…")
    for art in new_artifacts:
        add_artifact(s.artifacts_path, art)
    console.print(f"[green]✓[/green] Saved to {s.artifacts_path}")
    console.print()

    # Step 3: Reload corpus
    console.print("[bold]Step 3[/bold] Reloading corpus…")
    artifacts = load_artifacts(s.artifacts_path)
    console.print(f"[green]✓[/green] Corpus now has {len(artifacts)} artifacts")
    console.print()

    # Step 4: Researcher analyzes corpus
    entry_id = make_id("R")
    console.print(f"[bold]Step 4[/bold] Researcher analyzing corpus [dim]{entry_id}[/dim]…")
    
    # Load existing research questions
    existing_questions = load_research_questions(s.research_questions_path)
    if existing_questions:
        unanswered_count = sum(1 for q in existing_questions if not q.get('proposed_answer'))
        console.print(f"[dim]Loaded {len(existing_questions)} question(s), {unanswered_count} unanswered (will review ALL)[/dim]")
    
    t0 = time.perf_counter()
    with console.status(
    "[bold magenta]Researcher agent is analyzing the corpus…[/bold magenta]",
    spinner="dots",
    ):
        note, new_questions, updated_questions, glosses = analyze_corpus(
            model=s.ollama_researcher_model,
            entry_id=entry_id,
            artifacts=artifacts,
            existing_questions=existing_questions,
            max_hypotheses=s.max_researcher_hypotheses,
    )
    dt = time.perf_counter() - t0
    console.print(f"[green]✓[/green] Researcher done in {dt:.2f}s")
    console.print()

    # Step 5: Update artifact glosses
    if glosses:
        console.print(f"[bold]Step 5[/bold] Updating {len(glosses)} artifact gloss(es)…")
        updated = update_artifact_glosses(s.artifacts_path, glosses)
        console.print(f"[green]✓[/green] Updated {updated} artifact(s) in {s.artifacts_path}")
        console.print()
        # Reload to show updated glosses in final output
        artifacts = load_artifacts(s.artifacts_path)
    else:
        console.print("[dim]No glosses generated this cycle[/dim]")
        console.print()

    # Step 6: Context researcher analyzes sentences
    context_entry_id = make_id("C")
    console.print(f"[bold]Step 6[/bold] Context researcher analyzing sentences [dim]{context_entry_id}[/dim]…")
    
    t0_context = time.perf_counter()
    with console.status(
    "[bold cyan]Context researcher analyzing word usage in sentences…[/bold cyan]",
    spinner="dots",
    ):
        context_note = analyze_contextual_fit(
            model=s.ollama_researcher_model,
            entry_id=context_entry_id,
            artifacts=artifacts,
    )
    dt_context = time.perf_counter() - t0_context
    console.print(f"[green]✓[/green] Context researcher done in {dt_context:.2f}s")
    console.print()

    # Step 7: Save research notes
    console.print("[bold]Step 7[/bold] Saving research notes…")
    append_research_log(s.research_log_path, note)
    append_research_log(s.research_log_path, context_note)
    console.print(f"[green]✓[/green] Saved word analysis and context analysis to {s.research_log_path}")
    console.print()

    # Step 8: Save research questions
    if new_questions:
        console.print(f"[bold]Step 8[/bold] Saving {len(new_questions)} NEW research question(s)…")
        for q in new_questions:
            q["research_note_id"] = entry_id
            q["id"] = make_id("Q")
            q["created_at"] = int(time.time())
            append_research_question(s.research_questions_path, q)
        console.print(f"[green]✓[/green] Saved to {s.research_questions_path}")
        console.print()
    
    # Step 9: Update answered questions
    if updated_questions:
        console.print(f"[bold]Step 9[/bold] Updating {len(updated_questions)} answered question(s)…")
        updated_count = update_research_questions(s.research_questions_path, updated_questions)
        console.print(f"[green]✓[/green] Updated {updated_count} question(s) in {s.research_questions_path}")
        console.print()
    
    if not new_questions and not updated_questions:
        console.print("[yellow]![/yellow] No research questions generated or updated")
        console.print()

    # Final output
    console.print(Panel.fit(
        f"[bold]GHOSTROOT[/bold] ran 1 cycle\n"
        f"Backend: {s.backend}\n"
        f"Ollama bin: {s.ollama_bin}\n"
        f"Speaker model: {s.ollama_speaker_model}\n"
        f"Researcher model: {s.ollama_researcher_model}"
    ))

    console.print(Panel.fit(
        f"[bold]New artifacts[/bold]\n" +
        "\n---\n".join([
            f"ID: {art['id']}\n"
            f"Type: {art['type']}\n"
            f"Lang: {art['language']}\n"
            f"Text: {art['text']}\n"
            f"Discovery: {art['metadata']['discovery']}"
            for art in new_artifacts
        ])
    ))

    console.print(Panel.fit(
        f"[bold]Research note[/bold]\n"
        f"ID: {note['id']}\n"
        f"Artifacts in corpus: {note['metadata']['artifact_count']}\n\n"
        f"{note['summary']}"
    ))

    console.print(Panel.fit(
        f"[bold]Context Analysis[/bold]\n"
        f"ID: {context_note['id']}\n"
        f"Words analyzed: {context_note['metadata']['words_analyzed']}\n\n"
        f"{context_note['summary']}"
    ))

    if new_questions:
        q_text = "\n\n".join([
            f"[cyan]NEW Q{i+1}:[/cyan] {q.get('question', 'N/A')}\n"
            f"[dim]Answer:[/dim] {q.get('proposed_answer', '(unanswered)')}\n"
            f"[dim]Confidence:[/dim] {q.get('confidence', 'low')}"
            for i, q in enumerate(new_questions)
        ])
        console.print(Panel.fit(
            f"[bold]New Research Questions[/bold] ({len(new_questions)})\n\n{q_text}"
        ))
    
    if updated_questions:
        u_text = "\n\n".join([
            f"[green]ANSWERED:[/green] {q.get('question', 'N/A')}\n"
            f"[dim]Answer:[/dim] {q.get('proposed_answer', 'N/A')}\n"
            f"[dim]Confidence:[/dim] {q.get('confidence', 'unknown')}"
            for q in updated_questions
        ])
        console.print(Panel.fit(
            f"[bold]Answered Questions[/bold] ({len(updated_questions)})\n\n{u_text}"
        ))

    if glosses:
        # Get artifact details for formatting
        artifacts_for_display = load_artifacts(s.artifacts_path)
        artifacts_lookup = {a['id']: a for a in artifacts_for_display}
        
        gloss_lines = []
        for g in glosses:
            aid = g.get('artifact_id', '?')
            artifact = artifacts_lookup.get(aid, {})
            original_word = artifact.get('text', '?')
            meaning = g.get('meaning', 'N/A')
            gloss = g.get('gloss', '')
            confidence = g.get('confidence', '?')
            
            # Format: CODE 'original word': 'meaning' ('gloss if certain') level of certainty
            if gloss and gloss.strip():
                line = f"[cyan]{aid}[/cyan] '{original_word}': '{meaning}' ('{gloss}') [dim]{confidence}[/dim]"
            else:
                line = f"[cyan]{aid}[/cyan] '{original_word}': '{meaning}' [dim]{confidence}[/dim]"
            gloss_lines.append(line)
        
        gloss_text = "\n".join(gloss_lines)
        console.print(Panel.fit(
            f"[bold]Artifact Glosses Updated[/bold] ({len(glosses)})\n\n{gloss_text}"
        ))


if __name__ == "__main__":
    main()
