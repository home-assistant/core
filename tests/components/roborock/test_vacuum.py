"""Tests for Roborock vacuums."""
from unittest.mock import patch

from roborock.typing import RoborockCommand

from homeassistant.components.roborock.vacuum import (
    ATTR_MOP_INTENSITY_LIST,
    ATTR_MOP_MODE_LIST,
)
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform
from .mock_data import HOME_DATA

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = HOME_DATA.devices[0].duid


async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID


async def test_vacuum_services(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test vacuum services."""
    await setup_platform(hass, VACUUM_DOMAIN)
    # Test starting
    with patch("roborock.RoborockMqttClient.send_command") as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_START, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(
            DEVICE_ID, RoborockCommand.APP_START, None
        )
    # Test stopping
    with patch("roborock.RoborockMqttClient.send_command") as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_STOP, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(
            DEVICE_ID, RoborockCommand.APP_STOP, None
        )
    # Test pausing
    with patch("roborock.RoborockMqttClient.send_command") as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_PAUSE, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(
            DEVICE_ID, RoborockCommand.APP_PAUSE, None
        )
    # Test return to base
    with patch("roborock.RoborockMqttClient.send_command") as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_RETURN_TO_BASE,
            {"entity_id": ENTITY_ID},
            blocking=True,
        )
        mock_api_command.assert_called_once_with(
            DEVICE_ID, RoborockCommand.APP_CHARGE, None
        )
    # Test clean spot
    with patch("roborock.RoborockMqttClient.send_command") as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_CLEAN_SPOT, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(
            DEVICE_ID, RoborockCommand.APP_SPOT, None
        )
    # Test locate
    with patch("roborock.RoborockMqttClient.send_command") as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_LOCATE, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(
            DEVICE_ID, RoborockCommand.FIND_ME, None
        )


async def test_vacuum_fan_speeds(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test vacuum fan speeds."""
    await setup_platform(hass, VACUUM_DOMAIN)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get(ATTR_FAN_SPEED) == "balanced"

    fanspeeds = state.attributes.get(ATTR_FAN_SPEED_LIST)

    for speed in ["off", "silent", "balanced", "turbo", "max", "max_plus", "custom"]:
        assert speed in fanspeeds
    # Test setting fan speed to "Turbo"
    with patch(
        "homeassistant.components.roborock.vacuum.RoborockVacuum.send"
    ) as mock_send:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {"entity_id": ENTITY_ID, "fan_speed": "Turbo"},
            blocking=True,
        )
        mock_send.assert_called_once_with(RoborockCommand.SET_CUSTOM_MODE, [])


async def test_mop_modes(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test mop modes."""
    await setup_platform(hass, VACUUM_DOMAIN)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("mop_mode") == "standard"

    mop_modes = state.attributes.get(ATTR_MOP_MODE_LIST)

    for mode in ["standard", "deep", "deep_plus", "custom"]:
        assert mode in mop_modes
    # Test setting mop mode to "deep"
    with patch(
        "homeassistant.components.roborock.vacuum.RoborockVacuum.send"
    ) as mock_send:
        await hass.services.async_call(
            "Roborock",
            "vacuum_set_mop_mode",
            {"entity_id": ENTITY_ID, "mop_mode": "deep"},
            blocking=True,
        )
        mock_send.assert_called_once_with(RoborockCommand.SET_MOP_MODE, [301])


async def test_mop_intensity(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test mop intensity."""
    await setup_platform(hass, VACUUM_DOMAIN)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("mop_intensity") == "intense"

    mop_intensities = state.attributes.get(ATTR_MOP_INTENSITY_LIST)

    for intensity in ["off", "mild", "moderate", "intense", "custom"]:
        assert intensity in mop_intensities

    # Test setting intensity to "mild"
    with patch(
        "homeassistant.components.roborock.vacuum.RoborockVacuum.send"
    ) as mock_send:
        await hass.services.async_call(
            "Roborock",
            "vacuum_set_mop_intensity",
            {"entity_id": ENTITY_ID, "mop_intensity": "mild"},
            blocking=True,
        )
        mock_send.assert_called_once_with(
            RoborockCommand.SET_WATER_BOX_CUSTOM_MODE, [201]
        )
