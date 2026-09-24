# src/ghostroot/db.py
from __future__ import annotations

import sqlite3

# Tables land here as each MVP stage needs them (issues #8-13) -- only
# world_manifest exists so far (MVP 1: schema + world-seed generator).
# Full eventual schema: docs/ARCHITECTURE.md SS1/14.
SCHEMA = """
CREATE TABLE IF NOT EXISTS world_manifest (
    id                   INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton: one world per database
    world_seed           INTEGER NOT NULL,
    corpus_seed          INTEGER NOT NULL,
    mutation_seed        INTEGER NOT NULL,
    phonology_json       TEXT NOT NULL,  -- rolled consonant/vowel inventory, LANGUAGE.md
    syllable_shapes_json TEXT NOT NULL,  -- rolled syllable canon
    baseline_order_json  TEXT NOT NULL,  -- rolled baseline word order
    archetypes_json      TEXT NOT NULL,  -- rolled formula-archetype subset
    created_at           INTEGER NOT NULL  -- unix time the world was rolled
);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Creates every table this stage of the MVP needs."""
    conn.executescript(SCHEMA)
    conn.commit()
