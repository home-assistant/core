"""Test hassfest plugin loading and execution."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from typing import Literal

import pytest

from script.hassfest import bluetooth
from script.hassfest.model import Config
from script.hassfest.runner import run


@pytest.mark.parametrize(
    ("contents", "returncode", "output"),
    [
        ("{}", 0, "Invalid integrations: 0"),
        ("{", 1, "* [ERROR] [JSON] Invalid JSON file translations/en.json"),
    ],
)
def test_custom_plugin_selection(
    tmp_path: Path, contents: str, returncode: int, output: str
) -> None:
    """Custom validation loads only selected integration plugins and reports errors."""
    integration_path = tmp_path / "custom_components/test"
    translations_path = integration_path / "translations"
    translations_path.mkdir(parents=True)
    (integration_path / "manifest.json").write_text(
        json.dumps({"domain": "test", "name": "Test"})
    )
    (translations_path / "en.json").write_text(contents)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from script.hassfest.__main__ import main; "
            "result = main(); "
            "assert 'script.hassfest.json' in sys.modules; "
            "assert 'script.hassfest.metadata' not in sys.modules; "
            "assert 'script.hassfest.docker' not in sys.modules; "
            "assert 'script.hassfest.requirements' not in sys.modules; "
            "assert 'script.hassfest.translations' not in sys.modules; "
            "sys.exit(result)",
            "--integration-path",
            str(integration_path),
            "--plugins",
            "json,metadata,requirements",
            "--skip-plugins",
            "requirements",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == returncode, result.stderr
    assert output in result.stdout


def test_core_plugin_selection() -> None:
    """A Core run can select a Core-only plugin without importing other plugins."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from script.hassfest.__main__ import main; "
            "result = main(); "
            "assert 'script.hassfest.metadata' in sys.modules; "
            "assert 'script.hassfest.docker' not in sys.modules; "
            "assert 'script.hassfest.translations' not in sys.modules; "
            "sys.exit(result)",
            "--action",
            "validate",
            "--plugins",
            "metadata",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Validating metadata..." in result.stdout
    assert "Invalid integrations: 0" in result.stdout


@pytest.mark.parametrize(
    ("action", "returncode", "generated"),
    [("validate", 1, False), ("generate", 0, True)],
)
def test_fixable_errors(
    config: Config,
    tmp_path: Path,
    action: Literal["validate", "generate"],
    returncode: int,
    generated: bool,
) -> None:
    """Fixable errors fail validation but allow generation using the supplied plugins."""
    config = replace(config, root=tmp_path, action=action)
    integration_path = config.core_integrations_path / "test"
    integration_path.mkdir(parents=True)
    (integration_path / "manifest.json").write_text(
        json.dumps(
            {
                "domain": "test",
                "name": "Test",
                "bluetooth": [{"local_name": "Test-*"}],
            }
        )
    )
    generated_path = tmp_path / "homeassistant/generated/bluetooth.py"
    generated_path.parent.mkdir()
    generated_path.write_text("stale")

    assert run(config, [bluetooth]) == returncode

    assert ("Test-*" in generated_path.read_text()) is generated
