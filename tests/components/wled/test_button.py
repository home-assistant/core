"""Tests for the WLED button platform."""
from unittest.mock import MagicMock

from freezegun import freeze_time
import pytest
from wled import WLEDConnectionError, WLEDError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ENTITY_CATEGORY_CONFIG,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_button_restart(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the creation and values of the WLED button."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("button.wled_rgb_light_restart")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:restart"
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get("button.wled_rgb_light_restart")
    assert entry
    assert entry.unique_id == "aabbccddeeff_restart"
    assert entry.entity_category == ENTITY_CATEGORY_CONFIG

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
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED buttons."""
    mock_wled.reset.side_effect = WLEDError

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
    assert "Invalid response from API" in caplog.text


async def test_button_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED buttons."""
    mock_wled.reset.side_effect = WLEDConnectionError

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
    assert "Error communicating with API" in caplog.text


async def test_button_upgrade_stay_stable(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the upgrade button.

    There is both an upgrade for beta and stable available, however, the device
    is currently running a stable version. Therefore, the upgrade button should
    upgrade the the next stable (even though beta is newer).
    """
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("button.wled_rgb_light_upgrade")
    assert entry
    assert entry.unique_id == "aabbccddeeff_upgrade"
    assert entry.entity_category == ENTITY_CATEGORY_CONFIG

    state = hass.states.get("button.wled_rgb_light_upgrade")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:cellphone-arrow-down"
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wled_rgb_light_upgrade"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="0.12.0")


@pytest.mark.parametrize("mock_wled", ["wled/rgbw.json"], indirect=True)
async def test_button_upgrade_beta_to_stable(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the upgrade button.

    There is both an upgrade for beta and stable available the device
    is currently a beta, however, a newer stable is available. Therefore, the
    upgrade button should upgrade to the next stable.
    """
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wled_rgbw_light_upgrade"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="0.8.6")


@pytest.mark.parametrize("mock_wled", ["wled/rgb_single_segment.json"], indirect=True)
async def test_button_upgrade_stay_beta(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the upgrade button.

    There is an upgrade for beta and the device is currently a beta. Therefore,
    the upgrade button should upgrade to the next beta.
    """
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wled_rgb_light_upgrade"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="0.8.6b2")


@pytest.mark.parametrize("mock_wled", ["wled/rgb_websocket.json"], indirect=True)
async def test_button_no_upgrade_available(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the upgrade button. There is no update available."""
    state = hass.states.get("button.wled_websocket_upgrade")
    assert state
    assert state.state == STATE_UNAVAILABLE
