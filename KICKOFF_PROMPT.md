# Kickoff prompt for Claude Code (paste after starting `claude` in D:\India-econ-db, in plan mode)

Read CLAUDE.md, docs/rules.md and docs/memory.md, then skim docs/PRD.md, docs/architecture.md,
docs/phases.md and docs/design.md. The reference workbooks are in docs/reference/.

Decision update: PostgreSQL is now the database — local first (this Windows machine), later my
VPS. Supabase is no longer the primary database. Treat everything in docs/ as the source of truth;
if anything conflicts, ask me.

Do **Phase 0 only** (docs/phases.md):
1. Local PostgreSQL 16.14 is running on localhost:5432 and `psql` is on PATH. Another project's
   database (`rohingya_as_wb`) exists on the same server — never touch it.
   Propose the SQL to create database `econdb` and role `econdb_owner`, and ask before running it.
   I will run it myself or approve it, and I will type all passwords into `.env` myself —
   never ask me to paste a password into this chat.
2. Create the repository structure, pyproject/requirements, .venv, ruff, pytest, .gitignore,
   .env.example and a minimal `econdb` CLI with a `db-check` command.
3. Keep the existing `explore/` folder as reference; do not modify it.
4. Fill the [FILL] items you can determine in docs/memory.md and list the ones only I can answer.

Show me the plan first. After I approve and you finish, stop at the Phase 0 checkpoint,
show the evidence, update docs/memory.md, and commit as "Phase 0: project setup".
