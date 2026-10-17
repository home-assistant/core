"""Test the hassfest runner."""

from dataclasses import replace
import json
from pathlib import Path
from typing import Literal

from hassfest import bluetooth
from hassfest.model import Config
from hassfest.runner import run
import pytest


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
