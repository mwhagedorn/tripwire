"""End-to-end CLI tests driven through main(), with EeroClientAdapter replaced
by a fake so no test touches the real OS keyring or network."""

import tripwire.cli as cli_module
from tripwire.cli import main

NETWORKS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"networks": [{"id": 1001, "name": "Home", "status": "connected"}]},
}
EEROS_RESPONSE = {"meta": {"code": 200}, "data": []}
PROFILES_RESPONSE = {"meta": {"code": 200}, "data": []}
DEVICES_RESPONSE = {"meta": {"code": 200}, "data": []}


def _fake_adapter_class(
    *, authenticated=False, login_result=True, verify_result=True, logout_result=True
):
    class FakeAdapter:
        def __init__(self, cookie_file=None):
            self.is_authenticated = authenticated
            self.cookie_file = cookie_file

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            pass

        async def login(self, identifier):
            return login_result

        async def verify(self, code):
            return verify_result

        async def logout(self):
            return logout_result

        async def get_networks(self):
            return NETWORKS_RESPONSE

        async def get_eeros(self, network_id):
            return EEROS_RESPONSE

        async def get_profiles(self, network_id):
            return PROFILES_RESPONSE

        async def get_devices(self, network_id):
            return DEVICES_RESPONSE

    return FakeAdapter


def test_login_command_end_to_end(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class())

    exit_code = main(["login", "user@example.com"])

    assert exit_code == 0
    assert "Verification code requested" in capsys.readouterr().out


def test_verify_command_end_to_end(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class())

    exit_code = main(["verify", "123456"])

    assert exit_code == 0
    assert "Logged in." in capsys.readouterr().out


def test_logout_command_end_to_end(monkeypatch, capsys):
    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class())

    exit_code = main(["logout"])

    assert exit_code == 0
    assert "Logged out." in capsys.readouterr().out


def test_init_command_end_to_end(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class(authenticated=True))
    path = tmp_path / "baseline.json"

    exit_code = main(["init", "--baseline", str(path)])

    assert exit_code == 0
    assert path.exists()
    assert "Baseline created" in capsys.readouterr().out


def test_update_command_end_to_end(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class(authenticated=True))
    path = tmp_path / "baseline.json"
    main(["init", "--baseline", str(path)])
    capsys.readouterr()

    exit_code = main(["update", "--baseline", str(path)])

    assert exit_code == 0
    assert "Baseline updated" in capsys.readouterr().out


def test_check_command_end_to_end_reports_no_changes(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class(authenticated=True))
    path = tmp_path / "baseline.json"
    main(["init", "--baseline", str(path)])
    capsys.readouterr()

    exit_code = main(["check", "--baseline", str(path)])

    assert exit_code == 0
    assert "No changes." in capsys.readouterr().out


def test_init_fails_clearly_when_not_authenticated(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class(authenticated=False))
    path = tmp_path / "baseline.json"

    exit_code = main(["init", "--baseline", str(path)])

    assert exit_code == 1
    assert "Not logged in" in capsys.readouterr().err
    assert not path.exists()


def test_check_fails_clearly_when_not_authenticated(monkeypatch, capsys, tmp_path):
    path = tmp_path / "baseline.json"
    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class(authenticated=True))
    main(["init", "--baseline", str(path)])
    capsys.readouterr()

    monkeypatch.setattr(cli_module, "EeroClientAdapter", _fake_adapter_class(authenticated=False))
    exit_code = main(["check", "--baseline", str(path)])

    assert exit_code == 2
    assert "Not logged in" in capsys.readouterr().err
