"""Tests for the WLED button platform."""
from unittest.mock import MagicMock

from freezegun import freeze_time
import pytest
from wled import WLEDConnectionError, WLEDError

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    SERVICE_PRESS,
    ButtonDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry


async def test_button_restart(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the creation and values of the WLED button."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("button.wled_rgb_light_restart")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == ButtonDeviceClass.RESTART

    entry = entity_registry.async_get("button.wled_rgb_light_restart")
    assert entry
    assert entry.unique_id == "aabbccddeeff_restart"
    assert entry.entity_category is EntityCategory.CONFIG

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wled_rgb_light_restart"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.reset.call_count == 1
    mock_wled.reset.assert_called_with()


@freeze_time("2021-11-04 17:37:00", tz_offset=-1)
async def test_button_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test error handling of the WLED buttons."""
    mock_wled.reset.side_effect = WLEDError

    with pytest.raises(HomeAssistantError, match="Invalid response from WLED API"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wled_rgb_light_restart"},
            blocking=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("button.wled_rgb_light_restart")
    assert state
    assert state.state == "2021-11-04T16:37:00+00:00"


async def test_button_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test error handling of the WLED buttons."""
    mock_wled.reset.side_effect = WLEDConnectionError

    with pytest.raises(HomeAssistantError, match="Error communicating with WLED API"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wled_rgb_light_restart"},
            blocking=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("button.wled_rgb_light_restart")
    assert state
    assert state.state == STATE_UNAVAILABLE
