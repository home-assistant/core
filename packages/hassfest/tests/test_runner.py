"""Test the hassfest runner."""

from dataclasses import replace
import json
from types import ModuleType
from typing import Literal
from unittest.mock import Mock

from hassfest.model import Config, Integration
from hassfest.runner import run
import pytest


@pytest.mark.parametrize(
    ("action", "returncode", "generated"),
    [("validate", 1, False), ("generate", 0, True)],
)
def test_fixable_errors(
    config: Config,
    action: Literal["validate", "generate"],
    returncode: int,
    generated: bool,
) -> None:
    """Fixable errors fail validation but allow generation using supplied plugins."""
    config = replace(config, action=action)
    integration_path = config.core_integrations_path / "test"
    integration_path.mkdir(parents=True)
    (integration_path / "manifest.json").write_text(
        json.dumps({"domain": "test", "name": "Test"})
    )

    def validate(integrations: dict[str, Integration], config: Config) -> None:
        """Report a fixable error from an external plugin."""
        integrations["test"].add_error("test_plugin", "Outdated data", fixable=True)

    plugin = ModuleType("test_plugin")
    plugin.validate = validate
    plugin.generate = generate = Mock()

    assert run(config, [plugin]) == returncode
    assert generate.called is generated
