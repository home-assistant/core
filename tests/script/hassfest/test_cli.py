"""Test Core's hassfest plugin selection."""

import json
from pathlib import Path
import subprocess
import sys

import pytest


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
            "assert 'hassfest.json' in sys.modules; "
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


def test_null_codeowners(tmp_path: Path) -> None:
    """A null codeowners field reaches manifest validation without crashing."""
    integration_path = tmp_path / "custom_components/test"
    integration_path.mkdir(parents=True)
    (integration_path / "manifest.json").write_text(
        json.dumps(
            {
                "domain": "test",
                "name": "Test",
                "codeowners": None,
                "documentation": "https://example.com",
                "iot_class": "local_push",
                "version": "1.0.0",
            }
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "script.hassfest",
            "--integration-path",
            str(integration_path),
            "--plugins",
            "codeowners,manifest",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert (
        "[ERROR] [MANIFEST] Invalid manifest: expected a list at 'codeowners'. Got None"
        in result.stdout
    )
    assert "Traceback" not in result.stderr


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
