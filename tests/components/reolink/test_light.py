"""Test the Reolink light platform."""

from unittest.mock import MagicMock, call, patch

import pytest
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
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

from .conftest import TEST_CAM_NAME, TEST_NVR_NAME

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("whiteled_brightness", "expected_brightness", "color_temp"),
    [
        (100, 255, 3000),
        (None, None, None),
    ],
)
async def test_light_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    whiteled_brightness: int | None,
    expected_brightness: int | None,
    color_temp: int | None,
) -> None:
    """Test light entity state with floodlight."""

    def mock_supported(ch, capability):
        if capability == "color_temp":
            return color_temp is not None
        return True

    reolink_host.supported = mock_supported
    reolink_host.whiteled_state.return_value = True
    reolink_host.whiteled_brightness.return_value = whiteled_brightness
    reolink_host.whiteled_color_temperature.return_value = color_temp

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_CAM_NAME}_floodlight"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == expected_brightness
    if color_temp is not None:
        assert state.attributes["color_temp_kelvin"] == color_temp


async def test_light_turn_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test light turn off service."""
    reolink_host.whiteled_color_temperature.return_value = 3000

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_CAM_NAME}_floodlight"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_host.set_whiteled.assert_called_with(0, state=False)

    reolink_host.set_whiteled.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_light_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test light turn on service."""
    reolink_host.whiteled_color_temperature.return_value = 3000

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_CAM_NAME}_floodlight"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 51, ATTR_COLOR_TEMP_KELVIN: 4000},
        blocking=True,
    )
    reolink_host.set_whiteled.assert_has_calls(
        [call(0, brightness=20), call(0, state=True)]
    )
    reolink_host.baichuan.set_floodlight.assert_called_with(0, color_temp=4000)


@pytest.mark.parametrize(
    ("exception", "service_data"),
    [
        (ReolinkError("Test error"), {}),
        (ReolinkError("Test error"), {ATTR_BRIGHTNESS: 51}),
        (InvalidParameterError("Test error"), {ATTR_BRIGHTNESS: 51}),
    ],
)
async def test_light_turn_on_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    exception: Exception,
    service_data: dict,
) -> None:
    """Test light turn on service error cases."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.LIGHT}.{TEST_CAM_NAME}_floodlight"

    reolink_host.set_whiteled.side_effect = exception
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )


async def test_host_light_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test host light entity state with status led."""
    reolink_host.state_light = True

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
    reolink_host: MagicMock,
) -> None:
    """Test host light turn off service."""

    def mock_supported(ch, capability):
        if capability == "power_led":
            return False
        return True

    reolink_host.supported = mock_supported

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
    reolink_host.set_state_light.assert_called_with(False)

    reolink_host.set_state_light.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_host_light_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test host light turn on service."""

    def mock_supported(ch, capability):
        if capability == "power_led":
            return False
        return True

    reolink_host.supported = mock_supported

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
    reolink_host.set_state_light.assert_called_with(True)

    reolink_host.set_state_light.side_effect = ReolinkError("Test error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
