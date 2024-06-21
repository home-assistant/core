"""The test for the ecobee thermostat humidifier module."""

from unittest.mock import patch

import pytest

from homeassistant.components.ecobee.humidifier import MODE_MANUAL, MODE_OFF
from homeassistant.components.humidifier import (
    ATTR_AVAILABLE_MODES,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    MODE_AUTO,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    HumidifierDeviceClass,
    HumidifierEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .common import setup_platform

DEVICE_ID = "humidifier.ecobee"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the humidifier attributes are correct."""
    await setup_platform(hass, HUMIDIFIER_DOMAIN)

    state = hass.states.get(DEVICE_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 15
    assert state.attributes[ATTR_MIN_HUMIDITY] == DEFAULT_MIN_HUMIDITY
    assert state.attributes[ATTR_MAX_HUMIDITY] == DEFAULT_MAX_HUMIDITY
    assert state.attributes[ATTR_HUMIDITY] == 40
    assert state.attributes[ATTR_AVAILABLE_MODES] == [
        MODE_OFF,
        MODE_AUTO,
        MODE_MANUAL,
    ]
    assert state.attributes[ATTR_FRIENDLY_NAME] == "ecobee"
    assert state.attributes[ATTR_DEVICE_CLASS] == HumidifierDeviceClass.HUMIDIFIER
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == HumidifierEntityFeature.MODES


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test the humidifier can be turned on."""
    with patch("pyecobee.Ecobee.set_humidifier_mode") as mock_turn_on:
        await setup_platform(hass, HUMIDIFIER_DOMAIN)

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_on.assert_called_once_with(0, "manual")


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test the humidifier can be turned off."""
    with patch("pyecobee.Ecobee.set_humidifier_mode") as mock_turn_off:
        await setup_platform(hass, HUMIDIFIER_DOMAIN)

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: DEVICE_ID},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_off.assert_called_once_with(0, STATE_OFF)


async def test_set_mode(hass: HomeAssistant) -> None:
    """Test the humidifier can change modes."""
    with patch("pyecobee.Ecobee.set_humidifier_mode") as mock_set_mode:
        await setup_platform(hass, HUMIDIFIER_DOMAIN)

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: DEVICE_ID, ATTR_MODE: MODE_AUTO},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_once_with(0, MODE_AUTO)

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: DEVICE_ID, ATTR_MODE: MODE_MANUAL},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_with(0, MODE_MANUAL)

        with pytest.raises(ValueError):
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_SET_MODE,
                {ATTR_ENTITY_ID: DEVICE_ID, ATTR_MODE: "ModeThatDoesntExist"},
                blocking=True,
            )


async def test_set_humidity(hass: HomeAssistant) -> None:
    """Test the humidifier can set humidity level."""
    with patch("pyecobee.Ecobee.set_humidity") as mock_set_humidity:
        await setup_platform(hass, HUMIDIFIER_DOMAIN)

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: DEVICE_ID, ATTR_HUMIDITY: 60},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_humidity.assert_called_once_with(0, 60)
