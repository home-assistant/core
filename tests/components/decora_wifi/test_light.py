"""Tests for the Leviton Decora Wi-Fi light platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

ENTITY_ID = "light.living_room"


@pytest.mark.usefixtures("mock_decora_wifi")
@pytest.mark.parametrize(
    ("service", "translation_key"),
    [
        pytest.param(SERVICE_TURN_ON, "turn_on_failed", id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, "turn_off_failed", id="turn_off"),
    ],
)
async def test_action_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_switch: MagicMock,
    service: str,
    translation_key: str,
) -> None:
    """Test a failing switch update raises an error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_switch.update_attributes.side_effect = ValueError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
