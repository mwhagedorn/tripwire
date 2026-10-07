import pytest

from tripwire.cli import main


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    assert "usage: tripwire" in capsys.readouterr().out


def test_requires_a_command(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_check_requires_an_existing_baseline(tmp_path, capsys):
    path = tmp_path / "baseline.json"

    exit_code = main(["check", "--baseline", str(path)])

    assert exit_code == 2
    assert "no baseline found" in capsys.readouterr().err


def test_init_refuses_to_overwrite_existing_baseline_without_force(tmp_path, capsys):
    path = tmp_path / "baseline.json"
    path.write_text("{}")

    exit_code = main(["init", "--baseline", str(path)])

    assert exit_code == 1
    assert "already exists" in capsys.readouterr().err
    assert path.read_text() == "{}"


def test_update_requires_an_existing_baseline(tmp_path, capsys):
    path = tmp_path / "baseline.json"

    exit_code = main(["update", "--baseline", str(path)])

    assert exit_code == 1
    assert "no baseline found" in capsys.readouterr().err
    assert not path.exists()
