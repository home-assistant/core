"""Tests for the EnOcean switch platform."""
import math
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.enocean import DOMAIN as ENOCEAN_DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

_LIGHT_W_DIMMER_ENTITY_ID = f"{LIGHT_DOMAIN}.room0"
_LIGHT_W_DIMMER_SENDER_ID = [0xFF, 0xA5, 0x17, 0x0C]
_LIGHT_W_DIMMER_CONFIG = {
    LIGHT_DOMAIN: [
        {
            "platform": ENOCEAN_DOMAIN,
            "id": [0xDE, 0xAD, 0xBE, 0xEF],
            "sender_id": _LIGHT_W_DIMMER_SENDER_ID,
            "name": "room0",
            "brightness": 100,
        },
    ]
}

_LIGHT_W_DIMMER_NO_BRIGHTNESS_ENTITY_ID = f"{LIGHT_DOMAIN}.room_no_brightness_in_config"
_LIGHT_W_DIMMER_NO_BRIGHTNESS_SENDER_ID = [0xFF, 0xA5, 0x27, 0x0C]
_LIGHT_W_DIMMER_NO_BRIGHTNESS_CONFIG = {
    LIGHT_DOMAIN: [
        {
            "platform": ENOCEAN_DOMAIN,
            "id": [0xDE, 0xAD, 0xBE, 0xEF],
            "sender_id": _LIGHT_W_DIMMER_NO_BRIGHTNESS_SENDER_ID,
            "name": "room_no_brightness_in_config",
        },
    ]
}

# Non-dimmable light
_LIGHT_ENTITY_ID = f"{LIGHT_DOMAIN}.room1"
_LIGHT_SENDER_ID = [0xFF, 0xB5, 0x19, 0x0C]
_LIGHT_CONFIG = {
    LIGHT_DOMAIN: [
        {
            "platform": ENOCEAN_DOMAIN,
            "id": [0xDE, 0xAD, 0xBD, 0xEF],
            "sender_id": _LIGHT_SENDER_ID,
            "name": "room1",
            "color_mode": "onoff",
        },
    ]
}


@pytest.fixture
async def light_with_dimmer_no_brightness_in_config(hass):
    """Test fixture for dimmer that is missing brightness value in configuration."""
    assert await async_setup_component(
        hass, LIGHT_DOMAIN, _LIGHT_W_DIMMER_NO_BRIGHTNESS_CONFIG
    )
    await hass.async_block_till_done()


@pytest.fixture
async def light_with_dimmer_and_brightness_in_config(hass):
    """Test fixture for dimmer that has brightness value in configuration."""
    assert await async_setup_component(hass, LIGHT_DOMAIN, _LIGHT_W_DIMMER_CONFIG)
    await hass.async_block_till_done()


@pytest.fixture
async def light_without_dimmer(hass):
    """Test fixture for light that is not dimmable, i.e. on/off."""
    assert await async_setup_component(hass, LIGHT_DOMAIN, _LIGHT_CONFIG)
    await hass.async_block_till_done()


# Dimmer values
# https://www.eltako.com/fileadmin/downloads/en/_main_catalogue/Gesamt-Katalog_ChT_gb_lowRes.pdf
# Data telegrams DB3..DB0 must look like this, for example:
# 0x02, 0x32, 0x00, 0x09 (dimmer on at 50% and internal dimming speed)
# 0x02, 0x64, 0x01, 0x09 (dimmer on at 100% and fastest dimming speed)
# 0x02, 0x14, 0xFF, 0x09 (dimmer on at 20% and slowest dimming speed)
# 0x02, 0x.., 0x.., 0x08 (dimmer off)
@patch("homeassistant.components.enocean.device.EnOceanEntity.send_command")
async def test_dimmer_on(
    send_command: MagicMock,
    hass: HomeAssistant,
    light_with_dimmer_and_brightness_in_config,
) -> None:
    """Test turning dimmable light on when brightness level adjusted."""
    brightness = 75
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_W_DIMMER_ENTITY_ID, ATTR_BRIGHTNESS: brightness},
        blocking=True,
    )

    state = hass.states.get(_LIGHT_W_DIMMER_ENTITY_ID)
    assert state.state == STATE_ON

    # Assert the message sent to the device
    expected_cmd = [0xA5, 0x02, math.floor(brightness / 256 * 100), 0x01, 0x09]
    expected_bytes = expected_cmd + _LIGHT_W_DIMMER_SENDER_ID + [0]
    send_command.assert_called_once_with(expected_bytes, [], 1)


@patch("homeassistant.components.enocean.device.EnOceanEntity.send_command")
async def test_dimmer_on_brightness_from_config(
    send_command: MagicMock,
    hass: HomeAssistant,
    light_with_dimmer_and_brightness_in_config,
) -> None:
    """Test turning dimmable light on when brightness level set in configuration."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_W_DIMMER_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(_LIGHT_W_DIMMER_ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 100

    # Assert the message sent to the device
    expected_cmd = [0xA5, 0x02, math.floor(100 / 256 * 100), 0x01, 0x09]
    expected_bytes = expected_cmd + _LIGHT_W_DIMMER_SENDER_ID + [0]
    send_command.assert_called_once_with(expected_bytes, [], 1)


@patch("homeassistant.components.enocean.device.EnOceanEntity.send_command")
async def test_dimmer_on_no_brightness_in_config(
    send_command: MagicMock,
    hass: HomeAssistant,
    light_with_dimmer_no_brightness_in_config,
) -> None:
    """Test turning dimmable light on when no brightness level set in configuration."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_W_DIMMER_NO_BRIGHTNESS_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(_LIGHT_W_DIMMER_NO_BRIGHTNESS_ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 50

    # Assert the message sent to the device
    # Default brightness to 50% -> 128
    expected_cmd = [0xA5, 0x02, math.floor(50 / 256 * 100), 0x01, 0x09]
    expected_bytes = expected_cmd + _LIGHT_W_DIMMER_NO_BRIGHTNESS_SENDER_ID + [0]
    send_command.assert_called_once_with(expected_bytes, [], 1)


@patch("homeassistant.components.enocean.device.EnOceanEntity.send_command")
async def test_dimmer_off(
    send_command: MagicMock,
    hass: HomeAssistant,
    light_with_dimmer_and_brightness_in_config,
) -> None:
    """Test turning dimmable light off."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _LIGHT_W_DIMMER_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(_LIGHT_W_DIMMER_ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes.get("brightness") is None

    # Assert the message sent to the device
    expected_cmd = [0xA5, 0x02, 0, 0x00, 0x08]
    expected_bytes = expected_cmd + _LIGHT_W_DIMMER_SENDER_ID + [0]
    send_command.assert_called_once_with(expected_bytes, [], 1)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_W_DIMMER_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(_LIGHT_W_DIMMER_ENTITY_ID)
    assert state.state == STATE_ON
    assert (
        state.attributes.get("brightness") == 100
    )  # Remember the brightness set for device before turning off


@patch("homeassistant.components.enocean.device.EnOceanEntity.send_command")
async def test_light_on(
    send_command: MagicMock, hass: HomeAssistant, light_without_dimmer
) -> None:
    """Test turning light on - using on/off switch."""

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: _LIGHT_ENTITY_ID}, blocking=True
    )

    state = hass.states.get(_LIGHT_ENTITY_ID)
    assert state.state == STATE_ON

    # Assert the message sent to the device
    expected_cmd = [0xA5, 0x01, 0x00, 0x00, 0x09]
    expected_bytes = expected_cmd + _LIGHT_SENDER_ID + [0]
    send_command.assert_called_once_with(expected_bytes, [], 1)


@patch("homeassistant.components.enocean.device.EnOceanEntity.send_command")
async def test_light_off(
    send_command: MagicMock, hass: HomeAssistant, light_without_dimmer
) -> None:
    """Test turning light off - using on/off switch."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(_LIGHT_ENTITY_ID)
    assert state.state == STATE_OFF

    # Assert the message sent to the device
    expected_cmd = [0xA5, 0x01, 0x00, 0x00, 0x08]
    expected_bytes = expected_cmd + _LIGHT_SENDER_ID + [0]
    send_command.assert_called_once_with(expected_bytes, [], 1)
