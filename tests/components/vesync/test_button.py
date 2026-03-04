"""Tests for the button platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_clear_timer_button_press(
    hass: HomeAssistant,
    humidifier_600s_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test clear_timer button triggers clear_timer on the device."""
    button_entities = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, humidifier_600s_config_entry.entry_id
        )
        if e.domain == BUTTON_DOMAIN and "clear_timer" in (e.unique_id or "")
    ]
    assert len(button_entities) == 1
    entity_id = button_entities[0].entity_id

    with patch(
        "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.clear_timer",
        new_callable=AsyncMock,
    ) as clear_mock:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    clear_mock.assert_called_once()
