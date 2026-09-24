# tests/test_db.py
from __future__ import annotations

import sqlite3

import pytest

from ghostroot.db import create_schema


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    return conn


def _insert_world(conn: sqlite3.Connection, world_id: int = 1) -> None:
    conn.execute(
        """INSERT INTO world_manifest
           (id, world_seed, corpus_seed, mutation_seed,
            phonology_json, syllable_shapes_json, baseline_order_json,
            archetypes_json, created_at)
           VALUES (?, 1, 2, 3, '{}', '{}', '{}', '{}', 0)""",
        (world_id,),
    )
    conn.commit()


def test_create_schema_is_idempotent():
    conn = _connect()
    create_schema(conn)  # second call must not raise
    conn.close()


def test_world_manifest_accepts_one_row():
    conn = _connect()
    _insert_world(conn)
    row = conn.execute("SELECT world_seed, corpus_seed, mutation_seed FROM world_manifest").fetchone()
    assert row == (1, 2, 3)
    conn.close()


def test_world_manifest_rejects_a_second_row():
    conn = _connect()
    _insert_world(conn, world_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO world_manifest
               (id, world_seed, corpus_seed, mutation_seed,
                phonology_json, syllable_shapes_json, baseline_order_json,
                archetypes_json, created_at)
               VALUES (1, 99, 99, 99, '{}', '{}', '{}', '{}', 0)"""
        )
    conn.close()


def test_world_manifest_rejects_non_singleton_id():
    conn = _connect()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_world(conn, world_id=2)
    conn.close()
