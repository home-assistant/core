"""Tests for the blueprint init."""

from pathlib import Path
from unittest.mock import patch

from homeassistant.components import automation, blueprint
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_find_relevant_blueprints(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test finding relevant blueprints."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test_domain", "test_device")},
        name="Test Device",
    )
    entity_registry.async_get_or_create(
        "person",
        "test_domain",
        "test_entity",
        device_id=device.id,
        original_name="Test Person",
    )

    with patch.object(
        hass.config,
        "path",
        return_value=Path(automation.__file__).parent / "blueprints",
    ):
        automation.async_get_blueprints(hass)
        results = await blueprint.async_find_relevant_blueprints(hass, device.id)

    for matches in results.values():
        for match in matches:
            match["blueprint"] = match["blueprint"].name

    assert results == {
        "automation": [
            {
                "blueprint": "Motion-activated Light",
                "matched_input": {
                    "Person": [
                        "person.test_domain_test_entity",
                    ]
                },
            }
        ]
    }
