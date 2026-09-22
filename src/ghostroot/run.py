from __future__ import annotations

import argparse
import random
import re
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.status import Status


from ghostroot import beliefs as beliefs_store
from ghostroot import proto_hypotheses as hypotheses_store
from ghostroot.config import load_settings
from ghostroot.tools import (
    add_artifact,
    append_research_question,
    load_artifacts,
    load_research_questions,
    make_id,
    update_artifact_glosses,
    update_research_questions,
    write_research_log_entry,
)
from ghostroot.agents.speaker import generate_artifact
from ghostroot.agents.researcher import analyze_corpus, update_word_beliefs
from ghostroot.agents.context_researcher import analyze_contextual_fit

RESEARCH_FRUSTRATION_LIMIT = 3.0  # accumulated frustration before giving up on a batch
CONFIRMATION_RELIEF = 1.0  # a reinforced (or brand-new) belief fully offsets a pass's cost
CONTRADICTION_RELIEF = 0.5  # a revised belief is real work too, but only half as satisfying

# Weak signal for "the context researcher found something worth revising" --
# it doesn't (yet) write structured contradictions anywhere, just prose.
_CONTRADICTION_KEYWORDS = ("contradict", "inconsist", "reinterpret")


def _belief_snapshot(word_beliefs) -> dict:
    snapshot = {}
    for key, entry in word_beliefs["entries"].items():
        top = beliefs_store.top_interpretation(entry)
        snapshot[key] = (top[0], top[2]) if top else None  # (word_type, confidence)
    return snapshot


def _pass_outcome(before, word_beliefs, new_questions, updated_questions, context_note) -> str:
    """
    Classifies what an analysis pass actually achieved:
    - "confirmed": a lexeme got its first-ever interpretation, or an existing
      one's confidence rose without changing its word_type (reinforcement) --
      or a brand-new research question was raised.
    - "contradicted": an existing interpretation's word_type flipped or its
      confidence fell (a genuine revision), or an existing question's
      answer/confidence changed, or the context researcher flagged something.
    - "none": nothing changed at all.
    Confirmation takes priority if a pass produced both in different lexemes.
    """
    after = _belief_snapshot(word_beliefs)
    confirmed = False
    contradicted = False

    for key, after_val in after.items():
        before_val = before.get(key)
        if after_val == before_val:
            continue
        if before_val is None:
            confirmed = True  # first-ever interpretation
            continue
        before_type, before_conf = before_val
        after_type, after_conf = after_val
        if after_type == before_type and after_conf >= before_conf:
            confirmed = True
        else:
            contradicted = True

    if new_questions:
        confirmed = True
    if updated_questions:
        contradicted = True
    summary = (context_note.get("summary") or "").lower()
    if any(kw in summary for kw in _CONTRADICTION_KEYWORDS):
        contradicted = True

    if confirmed:
        return "confirmed"
    if contradicted:
        return "contradicted"
    return "none"


def run_research_pass(s, *, artifacts, existing_questions, word_beliefs, proto_hypotheses):
    """
    Runs one full analysis pass (researcher narrative + word-belief update +
    context check) over the given corpus and persists the results. Does not
    generate any new artifacts -- callers control acquisition of new material
    separately, so analysis can be repeated over the same corpus as many
    times as it keeps yielding something.

    Returns (artifacts, existing_questions, note, context_note, new_questions,
    updated_questions, glosses) -- artifacts/existing_questions are reloaded
    if they changed.
    """
    entry_id = make_id("R")
    note, new_questions, updated_questions = analyze_corpus(
        backend=s.backend,
        model=s.researcher_model,
        api_key=s.api_key,
        entry_id=entry_id,
        artifacts=artifacts,
        existing_questions=existing_questions,
        proto_hypotheses=proto_hypotheses,
        max_hypotheses=s.max_researcher_hypotheses,
    )
    hypotheses_store.save_hypotheses(s.proto_hypotheses_path, proto_hypotheses)

    glosses = update_word_beliefs(
        artifacts=artifacts,
        beliefs=word_beliefs,
        backend=s.backend,
        model=s.researcher_model,
        api_key=s.api_key,
    )
    beliefs_store.save_beliefs(s.word_beliefs_path, word_beliefs)
    if glosses:
        update_artifact_glosses(s.artifacts_path, glosses)
        artifacts = load_artifacts(s.artifacts_path)

    context_entry_id = make_id("C")
    context_note = analyze_contextual_fit(
        backend=s.backend,
        model=s.researcher_model,
        api_key=s.api_key,
        entry_id=context_entry_id,
        artifacts=artifacts,
    )

    write_research_log_entry(s.research_log_dir, note)
    write_research_log_entry(s.research_log_dir, context_note)

    if new_questions:
        for q in new_questions:
            q["research_note_id"] = entry_id
            q["id"] = make_id("Q")
            q["created_at"] = int(time.time())
            append_research_question(s.research_questions_path, q)
    if updated_questions:
        update_research_questions(s.research_questions_path, updated_questions)
    if new_questions or updated_questions:
        existing_questions = load_research_questions(s.research_questions_path)

    return artifacts, existing_questions, note, context_note, new_questions, updated_questions, glosses


def run_speaker_only(count: int) -> None:
    """Run only the speaker agent to generate artifacts."""
    console = Console()
    s = load_settings()

    console.print(Panel.fit(f"[bold]GHOSTROOT[/bold] Speaker-only mode ({count} runs)"))
    console.print(f"[dim]Backend:[/dim] {s.backend}")
    console.print(f"[dim]Word generator:[/dim] {s.word_generator}")
    console.print(f"[dim]Speaker model:[/dim] {s.speaker_model}")
    console.print(f"[dim]Branches:[/dim] {', '.join(s.branches)}")
    console.print()

    total_artifacts = 0

    for run in range(1, count + 1):
        # Round-robin through branches so cognates accumulate evenly across
        # descendant languages, instead of everything landing on one branch.
        language = s.branches[(run - 1) % len(s.branches)]
        console.print(f"[bold cyan]Run {run}/{count}[/bold cyan] [dim]({language})[/dim]")

        artifact_id = make_id("A")

        console.print(f"  ID: {artifact_id}")

        with console.status(
            "  [dim]Generating...[/dim]",
            spinner="dots",
        ):
            new_artifacts = generate_artifact(
                backend=s.backend,
                model=s.speaker_model,
                api_key=s.api_key,
                branch=language,
                artifact_id=artifact_id,
                max_words=s.max_speaker_words,
                word_generator=s.word_generator,
                proto_lexicon_path=s.proto_lexicon_path,
                word_beliefs_path=s.word_beliefs_path,
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


_RETRY_WAIT_PATTERN = re.compile(r"try again in ([\d.]+)s")


def _retry_wait_seconds(error_message: str, default: float) -> float:
    """
    Groq's 429 body names the exact wait (e.g. "Please try again in 8.87s").
    Use that when available instead of guessing a fixed backoff -- the rate
    limiter reserves tokens against the *requested* max_tokens ceiling, not
    actual usage, so a fixed guess is liable to undershoot.
    """
    match = _RETRY_WAIT_PATTERN.search(error_message)
    if match:
        return float(match.group(1)) + 1.0  # small margin
    return default


def _run_pass_with_retry(
    s, *, artifacts, existing_questions, word_beliefs, proto_hypotheses, console, max_retries=5, backoff_s=15
):
    """
    Running several analysis passes back-to-back easily trips a provider's
    rate limit (seen live on Groq's free tier: 8000 tokens/min, exhausted
    after 1-2 passes) -- back off and retry a few times instead of losing
    the whole batch to a single transient 429.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return run_research_pass(
                s, artifacts=artifacts, existing_questions=existing_questions,
                word_beliefs=word_beliefs, proto_hypotheses=proto_hypotheses,
            )
        except RuntimeError as e:
            if attempt == max_retries:
                raise
            wait_s = _retry_wait_seconds(str(e), backoff_s)
            console.print(f"  [red]![/red] LLM call failed ({e}); retrying in {wait_s:.0f}s ({attempt}/{max_retries})…")
            time.sleep(wait_s)


def run_research_only(count: int) -> None:
    """
    Runs up to `count` analysis-only passes over the EXISTING corpus -- no
    new artifacts generated. Stops early if a run of consecutive passes
    produces no progress (no belief confidence movement, no new/updated
    research questions, no flagged contradiction): acquiring new material is
    rare, so the material on hand should be exhausted before asking for more,
    rather than grinding a fixed number of passes over a corpus that has
    already given up everything it's going to.
    """
    console = Console()
    s = load_settings()

    console.print(Panel.fit(f"[bold]GHOSTROOT[/bold] Research-only mode (up to {count} passes)"))
    console.print(f"[dim]Backend:[/dim] {s.backend}")
    console.print(f"[dim]Researcher model:[/dim] {s.researcher_model}")
    console.print()

    artifacts = load_artifacts(s.artifacts_path)
    if not artifacts:
        console.print("[yellow]![/yellow] No artifacts in the corpus yet -- nothing to research.")
        return

    existing_questions = load_research_questions(s.research_questions_path)
    word_beliefs = beliefs_store.load_beliefs(s.word_beliefs_path)
    proto_hypotheses = hypotheses_store.load_hypotheses(s.proto_hypotheses_path)

    # Every pass costs 1 point up front; a confirmed belief fully refunds it
    # (resets the streak), a contradiction only half-refunds it (still real
    # work, but slowly accumulates even under nothing but revisions), and an
    # empty pass keeps the full cost.
    frustration = 0.0

    for pass_num in range(1, count + 1):
        console.print(f"[bold cyan]Pass {pass_num}/{count}[/bold cyan]")
        before = _belief_snapshot(word_beliefs)

        with console.status("  [dim]Analyzing...[/dim]", spinner="dots"):
            (
                artifacts,
                existing_questions,
                note,
                context_note,
                new_questions,
                updated_questions,
                glosses,
            ) = _run_pass_with_retry(
                s, artifacts=artifacts, existing_questions=existing_questions,
                word_beliefs=word_beliefs, proto_hypotheses=proto_hypotheses, console=console,
            )

        outcome = _pass_outcome(before, word_beliefs, new_questions, updated_questions, context_note)
        detail = (
            f"{len(glosses)} gloss(es), {len(new_questions)} new question(s), "
            f"{len(updated_questions)} updated question(s)"
        )

        frustration += 1.0
        if outcome == "confirmed":
            frustration = max(0.0, frustration - CONFIRMATION_RELIEF)
            console.print(f"  [green]✓[/green] confirmed (frustration {frustration:.1f}) ({detail})")
        elif outcome == "contradicted":
            frustration = max(0.0, frustration - CONTRADICTION_RELIEF)
            console.print(f"  [magenta]~[/magenta] contradicted/revised (frustration {frustration:.1f}) ({detail})")
        else:
            console.print(f"  [yellow]![/yellow] no progress (frustration {frustration:.1f}) ({detail})")

        console.print()

        if frustration >= RESEARCH_FRUSTRATION_LIMIT:
            console.print(Panel.fit(
                f"[bold yellow]Corpus exhausted for now[/bold yellow]\n"
                f"Frustration reached {frustration:.1f}/{RESEARCH_FRUSTRATION_LIMIT} "
                f"(stopped after {pass_num}/{count}).\n"
                f"Generate more material (e.g. `ghostroot --speaker N`) to continue."
            ))
            return

    console.print(Panel.fit(f"[bold green]Completed {count} research passes[/bold green]"))


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
    parser.add_argument(
        "-r", "--research",
        type=int,
        metavar="COUNT",
        help="Run up to COUNT analysis-only passes over the existing corpus (no new artifacts), "
             "stopping early once a batch stops making progress",
    )

    args = parser.parse_args()

    # Speaker-only mode
    if args.speaker:
        if args.speaker < 1:
            print("Error: Speaker count must be >= 1", file=sys.stderr)
            sys.exit(1)
        run_speaker_only(args.speaker)
        return

    # Research-only mode
    if args.research:
        if args.research < 1:
            print("Error: Research count must be >= 1", file=sys.stderr)
            sys.exit(1)
        run_research_only(args.research)
        return

    # Normal full cycle mode
    console = Console()
    s = load_settings()

    console.print(Panel.fit("[bold]GHOSTROOT[/bold] starting…"))
    console.print(f"[dim]Backend:[/dim] {s.backend}")
    console.print(f"[dim]Word generator:[/dim] {s.word_generator}")
    console.print(f"[dim]Speaker model:[/dim] {s.speaker_model}")
    console.print(f"[dim]Researcher model:[/dim] {s.researcher_model}")
    console.print(f"[dim]Branches:[/dim] {', '.join(s.branches)}")
    console.print()

    # Step 0: Load corpus
    console.print("[bold]Step 0[/bold] Loading artifact corpus…")
    artifacts = load_artifacts(s.artifacts_path)
    console.print(f"[green]✓[/green] Loaded {len(artifacts)} artifacts from {s.artifacts_path}")
    console.print()

    # Step 1: Speaker generates artifact
    language = random.choice(s.branches)
    artifact_id = make_id("A")
    console.print(f"[bold]Step 1[/bold] Speaker generating new artifact [dim]{artifact_id}[/dim]…")
    t0 = time.perf_counter()
    with console.status(
        "[bold cyan]Speaker agent is generating an inscription…[/bold cyan]",
        spinner="dots",
    ):
        new_artifacts = generate_artifact(
            backend=s.backend,
            model=s.speaker_model,
            api_key=s.api_key,
            branch=language,
            artifact_id=artifact_id,
            max_words=s.max_speaker_words,
            word_generator=s.word_generator,
            proto_lexicon_path=s.proto_lexicon_path,
            word_beliefs_path=s.word_beliefs_path,
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

    # Steps 4-9: researcher narrative + word beliefs + context check
    existing_questions = load_research_questions(s.research_questions_path)
    if existing_questions:
        unanswered_count = sum(1 for q in existing_questions if not q.get('proposed_answer'))
        console.print(f"[dim]Loaded {len(existing_questions)} question(s), {unanswered_count} unanswered (will review ALL)[/dim]")

    word_beliefs = beliefs_store.load_beliefs(s.word_beliefs_path)
    proto_hypotheses = hypotheses_store.load_hypotheses(s.proto_hypotheses_path)

    console.print(f"[bold]Step 4[/bold] Researcher analyzing corpus…")
    t0 = time.perf_counter()
    with console.status(
        "[bold magenta]Researcher agent is analyzing the corpus…[/bold magenta]",
        spinner="dots",
    ):
        (
            artifacts,
            existing_questions,
            note,
            context_note,
            new_questions,
            updated_questions,
            glosses,
        ) = _run_pass_with_retry(
            s, artifacts=artifacts, existing_questions=existing_questions,
            word_beliefs=word_beliefs, proto_hypotheses=proto_hypotheses, console=console,
        )
    dt = time.perf_counter() - t0
    console.print(f"[green]✓[/green] Researcher done in {dt:.2f}s")
    console.print()

    if glosses:
        console.print(f"[bold]Step 5[/bold] Updated {len(glosses)} artifact gloss(es) in {s.artifacts_path}")
    else:
        console.print("[dim]No glosses generated this cycle[/dim]")
    console.print()

    console.print(f"[bold]Step 6-7[/bold] Saved research notes to {s.research_log_dir}")
    console.print()

    if new_questions:
        console.print(f"[bold]Step 8[/bold] Saved {len(new_questions)} NEW research question(s)")
    if updated_questions:
        console.print(f"[bold]Step 9[/bold] Updated {len(updated_questions)} answered question(s)")
    if not new_questions and not updated_questions:
        console.print("[yellow]![/yellow] No research questions generated or updated")
    console.print()

    # Final output
    console.print(Panel.fit(
        f"[bold]GHOSTROOT[/bold] ran 1 cycle\n"
        f"Backend: {s.backend}\n"
        f"Speaker model: {s.speaker_model}\n"
        f"Researcher model: {s.researcher_model}"
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
