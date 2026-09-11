import pytest

from econdb.migrate import MIGRATIONS, checksum, pending


def test_crlf_and_lf_give_same_checksum(tmp_path):
    lf, crlf = tmp_path / "lf.sql", tmp_path / "crlf.sql"
    lf.write_bytes(b"CREATE SCHEMA a;\nCREATE SCHEMA b;\n")
    crlf.write_bytes(b"CREATE SCHEMA a;\r\nCREATE SCHEMA b;\r\n")
    assert checksum(lf) == checksum(crlf)


def test_pending_in_order_and_edit_detected(tmp_path):
    a, b = tmp_path / "0001_a.sql", tmp_path / "0002_b.sql"
    a.write_text("select 1;")
    b.write_text("select 2;")
    assert pending([b, a], {}) == [a, b]
    assert pending([a, b], {"0001": checksum(a)}) == [b]
    with pytest.raises(RuntimeError, match="changed after it was applied"):
        pending([a, b], {"0001": "stale"})


def test_duplicate_numbers_refused(tmp_path):
    a, b = tmp_path / "0001_a.sql", tmp_path / "0001_b.sql"
    a.write_text("")
    b.write_text("")
    with pytest.raises(RuntimeError, match="duplicate"):
        pending([a, b], {})


def test_repo_migrations_are_numbered_sequentially():
    versions = [f.name[:4] for f in sorted(MIGRATIONS.glob("*.sql"))]
    assert versions == [f"{i:04d}" for i in range(1, len(versions) + 1)]
