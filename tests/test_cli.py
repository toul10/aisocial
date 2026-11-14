import os
import stat

import pytest

from aisocial import __main__ as cli
from aisocial.config import is_valid_fernet_key


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    example = tmp_path / ".env.example"
    example.write_text("# AI Social\nAPP_SECRET=\n\n# optional\n# AISOCIAL_PORT=5050\n", encoding="utf-8")
    env = tmp_path / ".env"
    monkeypatch.setattr(cli, "ENV_PATH", env)
    monkeypatch.setattr(cli, "EXAMPLE_PATH", example)
    return env


def secret_in(path):
    return next(line.split("=", 1)[1] for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("APP_SECRET="))


def test_init_creates_env_from_example(env_file):
    assert cli.cmd_init(False) == 0
    text = env_file.read_text(encoding="utf-8")
    assert is_valid_fernet_key(secret_in(env_file)) and "# optional" in text
    if os.name != "nt":
        assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert cli.cmd_init(False) == 0
    assert env_file.read_text(encoding="utf-8") == text  # second run changes nothing


def test_new_key_keeps_a_backup(env_file):
    cli.cmd_init(False)
    old_text, old_secret = env_file.read_text(encoding="utf-8"), secret_in(env_file)
    assert cli.cmd_init(True) == 0
    assert (env_file.parent / ".env.bak").read_text(encoding="utf-8") == old_text
    assert secret_in(env_file) != old_secret and is_valid_fernet_key(secret_in(env_file))


def test_invalid_key_is_never_replaced_silently(env_file):
    env_file.write_text("APP_SECRET=garbage\n", encoding="utf-8")
    assert cli.cmd_init(False) == 1
    assert env_file.read_text(encoding="utf-8") == "APP_SECRET=garbage\n"


def test_empty_secret_is_filled_in(env_file):
    env_file.write_text("APP_SECRET=\nAISOCIAL_PORT=5051\n", encoding="utf-8")
    assert cli.cmd_init(False) == 0
    assert "AISOCIAL_PORT=5051" in env_file.read_text(encoding="utf-8")
    assert is_valid_fernet_key(secret_in(env_file))


def test_run_explains_config_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ENV_PATH", tmp_path / "missing.env")
    monkeypatch.delenv("APP_SECRET", raising=False)
    assert cli.cmd_run(False) == 2
    assert "APP_SECRET" in capsys.readouterr().err
