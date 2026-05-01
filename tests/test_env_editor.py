from pathlib import Path
from src.web.env_editor import read_env, write_env


def test_read_env_parses_key_value(tmp_path):
    env = tmp_path / ".env"
    env.write_text('FOO=bar\nBAZ=123\n')
    assert read_env(env) == {"FOO": "bar", "BAZ": "123"}


def test_read_env_strips_quotes(tmp_path):
    env = tmp_path / ".env"
    env.write_text('KEY="hello world"\n')
    assert read_env(env) == {"KEY": "hello world"}


def test_read_env_ignores_comments_and_blanks(tmp_path):
    env = tmp_path / ".env"
    env.write_text('# comment\nFOO=bar\n\nBAZ=1\n')
    assert read_env(env) == {"FOO": "bar", "BAZ": "1"}


def test_read_env_missing_file_returns_empty(tmp_path):
    assert read_env(tmp_path / "nonexistent.env") == {}


def test_write_env_updates_existing_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text('FOO=old\nBAR=keep\n')
    write_env(env, {"FOO": "new"})
    assert read_env(env) == {"FOO": "new", "BAR": "keep"}


def test_write_env_preserves_comments_and_order(tmp_path):
    env = tmp_path / ".env"
    env.write_text('# Camera settings\nFOO=old\nBAR=keep\n')
    write_env(env, {"FOO": "new"})
    content = env.read_text()
    assert content.startswith("# Camera settings\n")
    assert "FOO=new" in content
    assert "BAR=keep" in content


def test_write_env_appends_new_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text('FOO=bar\n')
    write_env(env, {"NEW_KEY": "value"})
    result = read_env(env)
    assert result["FOO"] == "bar"
    assert result["NEW_KEY"] == "value"


def test_write_env_no_tmp_file_left_behind(tmp_path):
    env = tmp_path / ".env"
    env.write_text('FOO=bar\n')
    write_env(env, {"FOO": "new"})
    assert not (tmp_path / ".env.tmp").exists()
    assert read_env(env)["FOO"] == "new"


def test_write_env_missing_file_creates_it(tmp_path):
    env = tmp_path / ".env"
    write_env(env, {"FOO": "bar"})
    assert read_env(env) == {"FOO": "bar"}


def test_read_env_quoted_value_with_apostrophe(tmp_path):
    env = tmp_path / ".env"
    env.write_text('KEY="it\'s fine"\n')
    assert read_env(env) == {"KEY": "it's fine"}
