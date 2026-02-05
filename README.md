# GHOSTROOT

**GHOSTROOT** is an agentic AI proof-of-concept that simulates the reconstruction of a lost proto-language from fragmentary evidence.

Rather than inventing a constructed language directly, GHOSTROOT models the **process of discovery**:
- extinct languages leave incomplete traces
- descendant languages diverge
- researchers argue, misinterpret, revise, and hypothesize

The system is designed to produce **uncertainty, disagreement, and evolving theories**, not correct answers.

---

## Concept

GHOSTROOT treats historical linguistics as an epistemic process:

- **Speaker agents** generate short inscriptions in descendant languages
- **Researcher agents** analyze the growing corpus
- Proto-language forms are reconstructed indirectly
- Hypotheses change as new artifacts appear

The language is never “finished”.
The reconstruction is always provisional.

---

## Project structure

```
ghostroot/
├── src/ghostroot/
│   ├── run.py
│   ├── config.py
│   ├── tools.py
│   └── agents/
│       ├── speaker.py
│       └── researcher.py
├── data/
│   ├── artifacts.json
│   └── research_log.json
├── tests/
├── .env
├── pyproject.toml
└── README.md
```

---

## Requirements

- Python 3.11+
- Ollama installed locally
- A local model pulled (e.g. `qwen3:4b`)

---

## Running

```
ghostroot
```

Each run:
1. Generates a new artifact
2. Appends it to the corpus
3. Re-analyzes the corpus
4. Records a new research note

Repeated runs create a growing scholarly trail.
