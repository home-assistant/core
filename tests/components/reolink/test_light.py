"""Test the Reolink light platform."""

from unittest.mock import MagicMock, call, patch

import pytest
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_NVR_NAME

from tests.common import MockConfigEntry


async def test_light_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test light entity state with floodlight."""
    reolink_connect.whiteled_state.return_value = True
    reolink_connect.whiteled_brightness.return_value = 100

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_NVR_NAME}_floodlight"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 255


async def test_light_brightness_none(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test light entity with floodlight and brightness returning None."""
    reolink_connect.whiteled_state.return_value = True
    reolink_connect.whiteled_brightness.return_value = None

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_NVR_NAME}_floodlight"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes["brightness"] is None


async def test_light_turn_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test light turn off service."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_NVR_NAME}_floodlight"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_connect.set_whiteled.assert_called_with(0, state=False)

    reolink_connect.set_whiteled.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    reolink_connect.set_whiteled.reset_mock(side_effect=True)


async def test_light_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test light turn on service."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_NVR_NAME}_floodlight"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 51},
        blocking=True,
    )
    reolink_connect.set_whiteled.assert_has_calls(
        [call(0, brightness=20), call(0, state=True)]
    )

    reolink_connect.set_whiteled.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    reolink_connect.set_whiteled.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 51},
            blocking=True,
        )

    reolink_connect.set_whiteled.side_effect = InvalidParameterError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 51},
            blocking=True,
        )

    reolink_connect.set_whiteled.reset_mock(side_effect=True)


async def test_host_light_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test host light entity state with status led."""
    reolink_connect.state_light = True

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_NVR_NAME}_status_led"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_host_light_turn_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test host light turn off service."""

    def mock_supported(ch, capability):
        if capability == "power_led":
            return False
        return True

    reolink_connect.supported = mock_supported

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_NVR_NAME}_status_led"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_connect.set_state_light.assert_called_with(False)

    reolink_connect.set_state_light.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    reolink_connect.set_state_light.reset_mock(side_effect=True)


async def test_host_light_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test host light turn on service."""

    def mock_supported(ch, capability):
        if capability == "power_led":
            return False
        return True

    reolink_connect.supported = mock_supported

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_NVR_NAME}_status_led"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_connect.set_state_light.assert_called_with(True)

    reolink_connect.set_state_light.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
