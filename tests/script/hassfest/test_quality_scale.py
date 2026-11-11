"""Tests for hassfest quality_scale."""

from pathlib import Path

from hassfest.model import Config, Integration
import pytest

from script.hassfest import quality_scale

DEVICE_ENTITY = """
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity


class TestEntity(Entity):
    def __init__(self) -> None:
        self._attr_device_info = DeviceInfo(identifiers={("test", "1")})
"""

INIT = """
async def async_setup_entry(hass, entry):
    return True


async def async_unload_entry(hass, entry):
    return True
"""


def _get_integration(
    tmp_path: Path,
    config: Config,
    rules: dict[str, str | dict[str, str]],
    files: dict[str, str],
) -> Integration:
    """Create an integration with a quality scale file and source files."""
    path = tmp_path / "test"
    path.mkdir()
    for name, content in files.items():
        (path / name).write_text(content)

    all_rules: dict[str, str | dict[str, str]] = {
        rule.name: {"status": "exempt", "comment": "Not relevant for this test"}
        for rule in quality_scale.ALL_RULES
    }
    all_rules.update(rules)
    lines = ["rules:"]
    for name, value in all_rules.items():
        if isinstance(value, str):
            lines.append(f"  {name}: {value}")
        else:
            lines.append(f"  {name}:")
            lines.extend(f"    {key}: {val}" for key, val in value.items())
    (path / "quality_scale.yaml").write_text("\n".join(lines) + "\n")

    return Integration(
        path,
        _config=config,
        _manifest={
            "domain": "test",
            "name": "Test",
            "documentation": "https://example.com",
            "codeowners": ["@awesome"],
            "quality_scale": "bronze",
        },
    )


@pytest.mark.usefixtures("mock_core_integration")
@pytest.mark.parametrize(
    ("rules", "files", "expected_errors"),
    [
        pytest.param(
            {"devices": "todo", "config-entry-unloading": "todo"},
            {"__init__.py": INIT, "entity.py": DEVICE_ENTITY},
            [
                "[config-entry-unloading] Rule is marked as todo, but the "
                "integration appears to implement it. Mark it as done, or add "
                "a comment explaining what is still missing",
                "[devices] Rule is marked as todo, but the integration appears "
                "to implement it. Mark it as done, or add a comment explaining "
                "what is still missing",
            ],
            id="todo_but_implemented",
        ),
        pytest.param(
            {
                "devices": {"status": "todo", "comment": "Not all entities"},
                "config-entry-unloading": {
                    "status": "todo",
                    "comment": "Not everything is cleaned up",
                },
            },
            {"__init__.py": INIT, "entity.py": DEVICE_ENTITY},
            [],
            id="todo_with_comment",
        ),
        pytest.param(
            {"devices": "todo", "config-entry-unloading": "todo"},
            {"__init__.py": "async def async_setup_entry(hass, entry): ..."},
            [],
            id="todo_not_implemented",
        ),
        pytest.param(
            {"devices": "done", "config-entry-unloading": "done"},
            {"__init__.py": INIT, "entity.py": DEVICE_ENTITY},
            [],
            id="done_and_implemented",
        ),
    ],
)
def test_todo_rule_implemented(
    config: Config,
    tmp_path: Path,
    rules: dict[str, str | dict[str, str]],
    files: dict[str, str],
    expected_errors: list[str],
) -> None:
    """Test that a bare todo for an implemented rule is flagged."""
    integration = _get_integration(tmp_path, config, rules, files)
    quality_scale.validate_iqs_file(config, integration)
    assert [error.error for error in integration.errors] == expected_errors


@pytest.mark.usefixtures("mock_core_integration")
def test_done_rule_not_implemented(config: Config, tmp_path: Path) -> None:
    """Test that a done rule that is not implemented is flagged."""
    integration = _get_integration(
        tmp_path,
        config,
        {"devices": "done", "config-entry-unloading": "done"},
        {"__init__.py": "async def async_setup_entry(hass, entry): ..."},
    )
    quality_scale.validate_iqs_file(config, integration)
    errors = {error.error for error in integration.errors}
    assert errors == {
        "[config-entry-unloading] Integration does not support config entry "
        f"unloading (is missing `async_unload_entry` in {integration.path / '__init__.py'})",
        quality_scale.RULE_URL.format(rule_name="config-entry-unloading"),
        "[devices] Integration does not create any devices (no `DeviceInfo`, "
        "`_attr_device_info` or `device_info` found)",
        quality_scale.RULE_URL.format(rule_name="devices"),
    }
