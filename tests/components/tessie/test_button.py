"""Test the Tessie button platform."""
from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_buttons(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the button entities are correct."""

    entry = await setup_platform(hass, [Platform.BUTTON])

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )

    for entity_id, func in [
        ("button.test_wake", "wake"),
        ("button.test_flash_lights", "flash_lights"),
        ("button.test_honk_horn", "honk"),
        ("button.test_homelink", "trigger_homelink"),
        ("button.test_keyless_driving", "enable_keyless_driving"),
        ("button.test_play_fart", "boombox"),
    ]:
        with patch(
            f"homeassistant.components.tessie.button.{func}",
        ) as mock_press:
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: [entity_id]},
                blocking=True,
            )
            mock_press.assert_called_once()
