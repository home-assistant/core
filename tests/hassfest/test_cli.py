"""Test reference-data selection for the packaged hassfest CLI."""

from pathlib import Path
import sys

from hassfest.model import Integration
from hassfest.plugins import INTEGRATION_PLUGINS
from hassfest.requirements import validate_custom_requirements
import pytest

from hassfest import cli
import homeassistant


def test_standalone_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Standalone validation uses the bundle and installed HA, not cwd files."""
    installed = tmp_path / "installed"
    module = installed / "hassfest"
    data = module / "_data"
    data.mkdir(parents=True)
    (data / "requirements.txt").write_text("aiohttp==3.13.0\n")
    (data / "requirements_all.txt").write_text("example==1.0\n")
    monkeypatch.setattr(cli, "__file__", str(module / "cli.py"))
    monkeypatch.setattr(
        homeassistant, "__file__", str(installed / "homeassistant/__init__.py")
    )
    monkeypatch.chdir(tmp_path)
    # These must not override the installed snapshot through implicit cwd lookup.
    (tmp_path / "requirements.txt").write_text("")
    (tmp_path / "requirements_all.txt").write_text("")
    monkeypatch.setattr(sys, "argv", ["hassfest", "--integration-path", str(tmp_path)])

    config = cli.get_config(INTEGRATION_PLUGINS, standalone=True)

    assert config.root == installed
    assert config.requirements_path == data
    assert config.core_integrations_path == installed / "homeassistant/components"
    integration = Integration(
        path=tmp_path,
        _config=config,
        _manifest={"domain": "example", "requirements": ["aiohttp==0.0.0"]},
    )
    assert not validate_custom_requirements(integration, config)
    assert "is a dependency of Home Assistant itself" in integration.errors[0].error


def test_explicit_core_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit checkout uses its current requirements rather than the bundle."""
    (tmp_path / "requirements.txt").write_text("new-core-dependency==1.0\n")
    (tmp_path / "requirements_all.txt").write_text("")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hassfest",
            "--integration-path",
            str(tmp_path),
            "--core-path",
            str(tmp_path),
        ],
    )

    config = cli.get_config(INTEGRATION_PLUGINS, standalone=True)

    assert config.root == tmp_path
    assert config.requirements_path is None
    integration = Integration(
        path=tmp_path,
        _config=config,
        _manifest={"domain": "example", "requirements": ["new-core-dependency==1.0"]},
    )
    assert not validate_custom_requirements(integration, config)


def test_standalone_requires_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """Standalone invocation cannot implicitly scan or generate installed Core."""
    monkeypatch.setattr(sys, "argv", ["hassfest"])
    with pytest.raises(SystemExit, match="2"):
        cli.get_config(INTEGRATION_PLUGINS, standalone=True)


@pytest.mark.parametrize("filename", ["requirements.txt", "requirements_all.txt"])
def test_incomplete_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    """A broken distribution fails instead of silently disabling requirement checks."""
    data = tmp_path / "_data"
    data.mkdir()
    (data / filename).write_text("")
    monkeypatch.setattr(cli, "__file__", str(tmp_path / "cli.py"))
    monkeypatch.setattr(sys, "argv", ["hassfest", "--integration-path", str(tmp_path)])
    with pytest.raises(RuntimeError, match="Bundled requirements are missing"):
        cli.get_config(INTEGRATION_PLUGINS, standalone=True)


def test_standalone_cannot_generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Supplying a checkout does not allow standalone generation."""
    (tmp_path / "requirements.txt").write_text("")
    (tmp_path / "requirements_all.txt").write_text("")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hassfest",
            "--integration-path",
            str(tmp_path),
            "--core-path",
            str(tmp_path),
            "--action",
            "generate",
        ],
    )
    with pytest.raises(RuntimeError, match="Generate is not allowed"):
        cli.get_config(INTEGRATION_PLUGINS, standalone=True)
