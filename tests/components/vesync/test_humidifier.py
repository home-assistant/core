"""Tests for VeSync humidifiers."""

from unittest.mock import patch

import pytest

from homeassistant.components.humidifier import (
    ATTR_AVAILABLE_MODES,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DOMAIN,
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HumidifierDeviceClass,
    HumidifierEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    STATE_ON,
)

TEST_HUMIDIFIER_ENTITIY = "humidifier.humidifier_300s"


async def test_attributes_humidifier(hass, setup_platform):
    """Test the humidifier attributes are correct."""
    state = hass.states.get(TEST_HUMIDIFIER_ENTITIY)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_MIN_HUMIDITY) == 30
    assert state.attributes.get(ATTR_MAX_HUMIDITY) == 80
    assert state.attributes.get(ATTR_HUMIDITY) == 40
    assert state.attributes.get(ATTR_AVAILABLE_MODES) == [
        MODE_NORMAL,
        MODE_AUTO,
        MODE_SLEEP,
    ]
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Humidifier 300s"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == HumidifierDeviceClass.HUMIDIFIER
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES) == HumidifierEntityFeature.MODES
    )


async def test_turn_on(hass, setup_platform):
    """Test the humidifier can be turned on."""
    with patch("pyvesync.vesyncfan.VeSyncHumid200300S.turn_on") as mock_turn_on:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_on.assert_called_once()


async def test_turn_off(hass, setup_platform):
    """Test the humidifier can be turned off."""
    with patch("pyvesync.vesyncfan.VeSyncHumid200300S.turn_off") as mock_turn_off:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_turn_off.assert_called_once()


async def test_set_mode(hass, setup_platform):
    """Test the humidifier can change modes."""
    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
    ) as mock_set_mode:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_AUTO},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_with(MODE_AUTO)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_NORMAL},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_with("manual")

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_SLEEP},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_with(MODE_SLEEP)

        with pytest.raises(ValueError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_MODE,
                {
                    ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY,
                    ATTR_MODE: "ModeThatDoesntExist",
                },
                blocking=True,
            )


async def test_set_humidity(hass, setup_platform):
    """Test the humidifier can set humidity level."""
    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity"
    ) as mock_set_humidity:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_HUMIDITY: 60},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_humidity.assert_called_once_with(60)
