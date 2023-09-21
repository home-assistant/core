"""Tests for the WLED button platform."""
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
from wled import WLEDConnectionError, WLEDError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
    pytest.mark.freeze_time("2021-11-04 17:36:59+01:00"),
]


async def test_button_restart(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_wled: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation and values of the WLED button."""
    assert (state := hass.states.get("button.wled_rgb_light_restart"))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot

    assert state.state == STATE_UNKNOWN
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wled_rgb_light_restart"},
        blocking=True,
    )
    assert mock_wled.reset.call_count == 1
    mock_wled.reset.assert_called_with()

    assert (state := hass.states.get("button.wled_rgb_light_restart"))
    assert state.state == "2021-11-04T16:37:00+00:00"

    # Test with WLED error
    mock_wled.reset.side_effect = WLEDError
    with pytest.raises(HomeAssistantError, match="Invalid response from WLED API"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wled_rgb_light_restart"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Ensure this didn't made the entity unavailable
    assert (state := hass.states.get("button.wled_rgb_light_restart"))
    assert state.state != STATE_UNAVAILABLE

    # Test with WLED connection error
    mock_wled.reset.side_effect = WLEDConnectionError
    with pytest.raises(HomeAssistantError, match="Error communicating with WLED API"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wled_rgb_light_restart"},
            blocking=True,
        )

    # Ensure this made the entity unavailable
    assert (state := hass.states.get("button.wled_rgb_light_restart"))
    assert state.state == STATE_UNAVAILABLE
