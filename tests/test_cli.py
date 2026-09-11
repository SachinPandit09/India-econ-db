import pytest

from econdb.cli import main


def test_help_lists_db_check(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "db-check" in capsys.readouterr().out


def test_db_check_without_database_url_fails_cleanly(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["db-check"]) == 1
    assert "DATABASE_URL is not set" in capsys.readouterr().err
