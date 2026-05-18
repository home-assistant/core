"""Tests for the Lepro light platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.lepro.const import DOMAIN
from homeassistant.components.lepro.light import LoproLight
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_light_state_on(hass: HomeAssistant) -> None:
    """Test that a light entity reflects the on state from the coordinator."""
    state = hass.states.get("light.living_room_light")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == round(800 / 1000 * 255)


@pytest.mark.usefixtures("init_integration")
async def test_light_state_off(hass: HomeAssistant) -> None:
    """Test that a light entity reflects the off state from the coordinator."""
    state = hass.states.get("light.bedroom_light")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_turn_on(
    hass: HomeAssistant,
    mock_lepro_api: MagicMock,
) -> None:
    """Test turning on a light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.bedroom_light"},
        blocking=True,
    )
    mock_lepro_api.async_turn_on.assert_called_once_with(67890)


@pytest.mark.usefixtures("init_integration")
async def test_turn_off(
    hass: HomeAssistant,
    mock_lepro_api: MagicMock,
) -> None:
    """Test turning off a light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.living_room_light"},
        blocking=True,
    )
    mock_lepro_api.async_turn_off.assert_called_once_with(12345)


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_lepro_api: MagicMock,
) -> None:
    """Test turning on a light with brightness."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.living_room_light", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    mock_lepro_api.async_set_brightness.assert_called_once_with(12345, 50)


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_with_color_temp(
    hass: HomeAssistant,
    mock_lepro_api: MagicMock,
) -> None:
    """Test turning on a light with color temperature."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.living_room_light", ATTR_COLOR_TEMP_KELVIN: 4000},
        blocking=True,
    )
    mock_lepro_api.async_set_color_temp.assert_called_once_with(12345, 4000)


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_with_rgb_color(
    hass: HomeAssistant,
    mock_lepro_api: MagicMock,
) -> None:
    """Test turning on a light with RGB color."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.living_room_light", ATTR_RGB_COLOR: (255, 0, 128)},
        blocking=True,
    )
    mock_lepro_api.async_set_color.assert_called_once_with(12345, (255, 0, 128))


@pytest.mark.usefixtures("init_integration")
async def test_handle_coordinator_update_missing_device(
    hass: HomeAssistant,
    mock_lepro_api: MagicMock,
) -> None:
    """Test _handle_coordinator_update does nothing when device data is missing."""
    state_before = hass.states.get("light.living_room_light")
    assert state_before is not None

    # Simulate a coordinator update with the device absent from data
    mock_lepro_api.async_get_devices = AsyncMock(return_value=[])
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data
    coordinator.data = {}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    # State should remain unchanged (no crash)
    state_after = hass.states.get("light.living_room_light")
    assert state_after is not None


async def test_async_update_fetches_device_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_lepro_api: MagicMock,
) -> None:
    """Test async_update fetches and applies fresh device state."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data

    mock_lepro_api.async_get_device_state = AsyncMock(
        return_value={
            "did": 12345,
            "name": "Living Room Light",
            "switch": 0,
            "brightness": 200,
            "temp": 0,
        }
    )

    # Create entity attached to the coordinator (but not to hass entity registry)
    entity = LoproLight(coordinator, 12345)
    # async_update with no entity_id is OK as long as async_write_ha_state is not reached
    # We test by monkeypatching async_write_ha_state
    entity.async_write_ha_state = MagicMock()
    await entity.async_update()

    assert entity._attr_is_on is False
    entity.async_write_ha_state.assert_called_once()


async def test_async_update_handles_exception(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_lepro_api: MagicMock,
) -> None:
    """Test async_update logs a debug message and returns on API error."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data

    entity = LoproLight(coordinator, 12345)
    entity.async_write_ha_state = MagicMock()

    mock_lepro_api.async_get_device_state = AsyncMock(
        side_effect=Exception("API error")
    )
    await entity.async_update()
    # Should not raise — exception is caught and logged
    entity.async_write_ha_state.assert_not_called()


async def test_async_update_skipped_when_disabled(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_lepro_api: MagicMock,
) -> None:
    """Test that async_update returns early when the entity is disabled."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data

    entity = LoproLight(coordinator, 12345)
    entity.async_write_ha_state = MagicMock()

    with patch.object(
        type(entity), "enabled", new_callable=PropertyMock, return_value=False
    ):
        await entity.async_update()

    mock_lepro_api.async_get_device_state.assert_not_called()
