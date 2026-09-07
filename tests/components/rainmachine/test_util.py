"""Test RainMachine utilities."""

from unittest.mock import patch

from homeassistant.components.rainmachine.util import (
    get_automations_and_scripts_using_entity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def test_get_automations_and_scripts_using_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test formatting automation and script references to an entity."""
    entity_registry.async_get_or_create(
        "automation",
        "automation",
        "automation-uid",
        suggested_object_id="linked",
        original_name="Linked automation",
    )
    entity_registry.async_get_or_create(
        "script",
        "script",
        "script-uid",
        suggested_object_id="linked",
        original_name="Linked script",
    )

    with (
        patch(
            "homeassistant.components.rainmachine.util.automations_with_entity",
            return_value=["automation.linked"],
        ),
        patch(
            "homeassistant.components.rainmachine.util.scripts_with_entity",
            return_value=["script.linked", "script.missing"],
        ),
    ):
        items = get_automations_and_scripts_using_entity(
            hass, "switch.12345_landscaping"
        )

    assert items == [
        "- [Linked automation](/config/automation/edit/automation-uid)",
        "- [Linked script](/config/script/edit/script-uid)",
        "- `script.missing`",
    ]
