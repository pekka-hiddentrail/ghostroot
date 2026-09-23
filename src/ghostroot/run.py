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
from ghostroot import report
from ghostroot.config import load_settings
from ghostroot.tools import (
    add_artifact,
    load_artifacts,
    make_id,
    update_artifact_glosses,
    write_research_log_entry,
)
from ghostroot.agents.speaker import generate_artifact
from ghostroot.agents.researcher import analyze_corpus, update_word_beliefs
from ghostroot.agents.context_researcher import analyze_contextual_fit

RESEARCH_FRUSTRATION_LIMIT = 3.0  # accumulated frustration before giving up on a batch
CONFIRMATION_RELIEF = 1.0  # a reinforced (or brand-new) belief fully offsets a pass's cost
CONTRADICTION_RELIEF = 0.5  # a revised belief is real work too, but only half as satisfying


def _belief_snapshot(word_beliefs) -> dict:
    snapshot = {}
    for key, entry in word_beliefs["entries"].items():
        top = beliefs_store.top_interpretation(entry)
        snapshot[key] = (top[0], top[2]) if top else None  # (word_type, confidence)
    return snapshot


def _pass_outcome(before, word_beliefs, contradictions_found: int = 0) -> str:
    """
    Classifies what an analysis pass actually achieved:
    - "confirmed": a lexeme got its first-ever interpretation, or an existing
      one's confidence rose without changing its word_type (reinforcement).
    - "contradicted": an existing interpretation's word_type flipped or its
      confidence fell (a genuine revision), or the context researcher found
      a genuine contradiction (contradictions_found > 0 -- see
      _apply_context_contradictions).
    - "none": nothing changed at all.
    Confirmation takes priority if a pass produced both in different lexemes.
    """
    after = _belief_snapshot(word_beliefs)
    confirmed = False
    contradicted = contradictions_found > 0

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

    if confirmed:
        return "confirmed"
    if contradicted:
        return "contradicted"
    return "none"


def _apply_context_contradictions(word_beliefs, contradictions):
    """
    Registers each genuine context contradiction (see
    context_researcher.analyze_contextual_fit) as real evidence_against on
    the CURRENT top interpretation of the belief it disagrees with. This is
    what actually closes the loop between the context check and the belief
    store -- a contradiction used to just sit in the log as prose with no
    mechanical effect. Lowering that belief's confidence also naturally makes
    update_word_beliefs prioritize it again next pass (it already reviews the
    lowest-confidence lexemes first), so no separate "flagged for re-review"
    bookkeeping is needed on top of this.

    Returns gloss updates (same shape as update_word_beliefs's return) for
    any entry whose top interpretation changed as a result.
    """
    updates = []
    for c in contradictions:
        key = beliefs_store.key_for(c["branch"], c["form"])
        entry = word_beliefs["entries"].get(key)
        if entry is None:
            continue
        top = beliefs_store.top_interpretation(entry)
        if top is None:
            continue
        top_word_type = top[0]
        beliefs_store.record_interpretation(entry, word_type=top_word_type, meaning="", supports=False)

        new_top = beliefs_store.top_interpretation(entry)
        if not new_top:
            continue
        new_word_type, new_bucket, new_conf = new_top
        for artifact_id in entry["artifact_ids"]:
            updates.append({
                "artifact_id": artifact_id,
                "meaning": new_bucket["meaning"],
                "gloss": new_bucket["gloss"],
                "confidence": new_conf,
                "word_type": new_word_type,
            })
    return updates


def run_research_pass(s, *, artifacts, word_beliefs, proto_hypotheses):
    """
    Runs one full analysis pass (researcher narrative + word-belief update +
    context check) over the given corpus and persists the results as ONE
    combined research-log entry. Does not generate any new artifacts --
    callers control acquisition of new material separately, so analysis can
    be repeated over the same corpus as many times as it keeps yielding
    something.

    Returns (artifacts, note, context_note, glosses) -- artifacts is reloaded
    if it changed.
    """
    entry_id = make_id("R")
    note = analyze_corpus(
        backend=s.backend,
        model=s.researcher_model,
        api_key=s.api_key,
        entry_id=entry_id,
        artifacts=artifacts,
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
    if glosses:
        update_artifact_glosses(s.artifacts_path, glosses)
        artifacts = load_artifacts(s.artifacts_path)

    context_note, contradictions = analyze_contextual_fit(
        backend=s.backend,
        model=s.researcher_model,
        api_key=s.api_key,
        entry_id=entry_id,
        artifacts=artifacts,
    )

    contradiction_updates = _apply_context_contradictions(word_beliefs, contradictions)
    if contradiction_updates:
        update_artifact_glosses(s.artifacts_path, contradiction_updates)
        artifacts = load_artifacts(s.artifacts_path)
        glosses = glosses + contradiction_updates

    beliefs_store.save_beliefs(s.word_beliefs_path, word_beliefs)

    combined_entry = {
        "id": entry_id,
        "type": "analysis",
        "summary": (
            "# Research Findings\n\n" + note["summary"] +
            "\n\n---\n\n# Context Check\n\n" + context_note["summary"]
        ),
        "metadata": {**note["metadata"], **context_note["metadata"]},
    }
    write_research_log_entry(s.research_log_dir, combined_entry)

    return artifacts, note, context_note, glosses


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


def _run_pass_with_retry(s, *, artifacts, word_beliefs, proto_hypotheses, console, max_retries=5, backoff_s=15):
    """
    Running several analysis passes back-to-back easily trips a provider's
    rate limit (seen live on Groq's free tier: 8000 tokens/min, exhausted
    after 1-2 passes) -- back off and retry a few times instead of losing
    the whole batch to a single transient 429.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return run_research_pass(
                s, artifacts=artifacts, word_beliefs=word_beliefs, proto_hypotheses=proto_hypotheses,
            )
        except RuntimeError as e:
            if attempt == max_retries:
                raise
            wait_s = _retry_wait_seconds(str(e), backoff_s)
            console.print(f"  [red]![/red] LLM call failed ({e}); retrying in {wait_s:.0f}s ({attempt}/{max_retries})…")
            time.sleep(wait_s)


def _run_research_rounds(s, *, artifacts, word_beliefs, proto_hypotheses, console, max_rounds):
    """
    Shared frustration-scored analysis loop: runs up to `max_rounds` passes
    over `artifacts`, stopping early once a run of passes stops making
    progress. Used by both standalone --research mode and each cycle of
    --cycles mode.

    Returns (artifacts, rounds_run, stopped_early).
    """
    # Every pass costs 1 point up front; a confirmed belief fully refunds it
    # (resets the streak), a contradiction only half-refunds it (still real
    # work, but slowly accumulates even under nothing but revisions), and an
    # empty pass keeps the full cost.
    frustration = 0.0

    for pass_num in range(1, max_rounds + 1):
        console.print(f"[bold cyan]Research round {pass_num}/{max_rounds}[/bold cyan]")
        before = _belief_snapshot(word_beliefs)

        with console.status("  [dim]Analyzing...[/dim]", spinner="dots"):
            artifacts, note, context_note, glosses = _run_pass_with_retry(
                s, artifacts=artifacts, word_beliefs=word_beliefs,
                proto_hypotheses=proto_hypotheses, console=console,
            )

        contradictions_found = context_note.get("metadata", {}).get("contradictions_found", 0)
        outcome = _pass_outcome(before, word_beliefs, contradictions_found)
        detail = f"{len(glosses)} gloss(es)"

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
                f"(stopped after {pass_num}/{max_rounds})."
            ))
            return artifacts, pass_num, True

    return artifacts, max_rounds, False


def run_research_only(count: int) -> None:
    """
    Runs up to `count` analysis-only passes over the EXISTING corpus -- no
    new artifacts generated. Stops early if a run of consecutive passes
    produces no progress (no belief confidence movement, no flagged
    contradiction): acquiring new material is rare, so the material on hand
    should be exhausted before asking for more, rather than grinding a fixed
    number of passes over a corpus that has already given up everything
    it's going to.
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

    word_beliefs = beliefs_store.load_beliefs(s.word_beliefs_path)
    proto_hypotheses = hypotheses_store.load_hypotheses(s.proto_hypotheses_path)

    _artifacts, rounds_run, stopped_early = _run_research_rounds(
        s, artifacts=artifacts, word_beliefs=word_beliefs,
        proto_hypotheses=proto_hypotheses, console=console, max_rounds=count,
    )
    if not stopped_early:
        console.print(Panel.fit(f"[bold green]Completed {count} research passes[/bold green]"))
    else:
        console.print(f"[dim]Generate more material (e.g. `ghostroot --speaker N`) to continue.[/dim]")


def run_full_cycles(*, cycles: int, words: int, rounds: int) -> None:
    """
    Repeats a full (bootstrap -> research -> report) sequence `cycles`
    times, accumulating the corpus across cycles:
      1. Bootstrap `words` new artifacts (speaker only, round-robin branches).
      2. Run up to `rounds` research-only passes over the growing corpus
         (same frustration-scored early stop as standalone --research mode).
      3. Write a cycle-level report (data/reports/cycle_NNN.md) -- corpus
         stats, the full proto-root hypothesis table, and top lexeme
         beliefs -- rendered from a fixed template so cycle N is directly
         comparable against cycle N-1.
    """
    console = Console()
    s = load_settings()

    console.print(Panel.fit(
        f"[bold]GHOSTROOT[/bold] Full-cycle mode "
        f"({cycles} cycle(s): {words} word(s)/sentence(s) + up to {rounds} research round(s) each)"
    ))
    console.print(f"[dim]Backend:[/dim] {s.backend}")
    console.print(f"[dim]Word generator:[/dim] {s.word_generator}")
    console.print(f"[dim]Branches:[/dim] {', '.join(s.branches)}")
    console.print()

    for cycle_num in range(1, cycles + 1):
        console.print(Panel.fit(f"[bold]Cycle {cycle_num}/{cycles}[/bold]"))

        # Phase 1: bootstrap words/sentences
        console.print(f"[bold]Phase 1[/bold] Generating {words} artifact(s)…")
        for run in range(1, words + 1):
            language = s.branches[(run - 1) % len(s.branches)]
            artifact_id = make_id("A")
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
            for art in new_artifacts:
                add_artifact(s.artifacts_path, art)
        console.print(f"[green]✓[/green] Bootstrapped {words} run(s)")
        console.print()

        # Phase 2: research rounds
        console.print(f"[bold]Phase 2[/bold] Research rounds (up to {rounds})")
        artifacts = load_artifacts(s.artifacts_path)
        word_beliefs = beliefs_store.load_beliefs(s.word_beliefs_path)
        proto_hypotheses = hypotheses_store.load_hypotheses(s.proto_hypotheses_path)

        artifacts, rounds_run, stopped_early = _run_research_rounds(
            s, artifacts=artifacts, word_beliefs=word_beliefs,
            proto_hypotheses=proto_hypotheses, console=console, max_rounds=rounds,
        )
        console.print(f"[green]✓[/green] Ran {rounds_run}/{rounds} research round(s)"
                      + (" (stopped early)" if stopped_early else ""))
        console.print()

        # Phase 3: cycle report
        console.print(f"[bold]Phase 3[/bold] Writing cycle report…")
        report_content = report.render_cycle_report(
            cycle_number=cycle_num, artifacts=artifacts,
            word_beliefs=word_beliefs, proto_hypotheses=proto_hypotheses,
        )
        report_path = report.write_cycle_report(s.reports_dir, cycle_num, report_content)
        console.print(f"[green]✓[/green] Saved to {report_path}")
        console.print()

        console.print(Panel.fit(report_content))
        console.print()

    console.print(Panel.fit(f"[bold green]Completed {cycles} cycle(s)[/bold green]"))


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
    parser.add_argument(
        "--cycles",
        type=int,
        metavar="COUNT",
        help="Run COUNT full cycles, each: bootstrap --words artifacts, then up to --rounds "
             "research-only passes, then write a cycle report to data/reports/",
    )
    parser.add_argument(
        "--words",
        type=int,
        default=10,
        metavar="COUNT",
        help="Artifacts to bootstrap per cycle in --cycles mode (default: 10)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        metavar="COUNT",
        help="Max research-only passes per cycle in --cycles mode (default: 3)",
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

    # Full-cycle mode (bootstrap -> research rounds -> report, repeated)
    if args.cycles:
        if args.cycles < 1:
            print("Error: Cycles count must be >= 1", file=sys.stderr)
            sys.exit(1)
        if args.words < 1:
            print("Error: Words count must be >= 1", file=sys.stderr)
            sys.exit(1)
        if args.rounds < 1:
            print("Error: Rounds count must be >= 1", file=sys.stderr)
            sys.exit(1)
        run_full_cycles(cycles=args.cycles, words=args.words, rounds=args.rounds)
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

    # Steps 4-7: researcher narrative + word beliefs + context check
    word_beliefs = beliefs_store.load_beliefs(s.word_beliefs_path)
    proto_hypotheses = hypotheses_store.load_hypotheses(s.proto_hypotheses_path)

    console.print(f"[bold]Step 4[/bold] Researcher analyzing corpus…")
    t0 = time.perf_counter()
    with console.status(
        "[bold magenta]Researcher agent is analyzing the corpus…[/bold magenta]",
        spinner="dots",
    ):
        artifacts, note, context_note, glosses = _run_pass_with_retry(
            s, artifacts=artifacts, word_beliefs=word_beliefs,
            proto_hypotheses=proto_hypotheses, console=console,
        )
    dt = time.perf_counter() - t0
    console.print(f"[green]✓[/green] Researcher done in {dt:.2f}s")
    console.print()

    if glosses:
        console.print(f"[bold]Step 5[/bold] Updated {len(glosses)} artifact gloss(es) in {s.artifacts_path}")
    else:
        console.print("[dim]No glosses generated this cycle[/dim]")
    console.print()

    console.print(f"[bold]Step 6[/bold] Saved combined research note to {s.research_log_dir}")
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
