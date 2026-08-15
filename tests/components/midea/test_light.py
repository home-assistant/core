"""Tests for midea light.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.x13 import DeviceAttributes as X13Attributes
from midealocal.exceptions import SocketException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform

X13_EFFECTS = ["Manual", "Living", "Reading", "Mildly", "Cinema", "Night"]


def _x13_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.X13,
        attributes={
            X13Attributes.power: True,
            X13Attributes.brightness: 128,
            X13Attributes.color_temperature: 4000,
            X13Attributes.effect: "Manual",
            X13Attributes.rgb_color: None,
        },
    )
    device.color_temp_range = [2700, 6500]
    device.effects = X13_EFFECTS
    return device


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test async_setup_entry creates the light entity for an X13 device."""
    device = _x13_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_light_state_and_services(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test light state attributes and service calls reach the device."""
    device = _x13_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 4000
    assert state.attributes[ATTR_MIN_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_MAX_COLOR_TEMP_KELVIN] == 6500
    assert state.attributes[ATTR_EFFECT] == "Manual"
    assert state.attributes[ATTR_EFFECT_LIST] == X13_EFFECTS
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.COLOR_TEMP]

    device.calls.clear()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_entry.entity_id,
            ATTR_BRIGHTNESS: 200,
            ATTR_COLOR_TEMP_KELVIN: 5000,
            ATTR_EFFECT: "Cinema",
        },
        blocking=True,
    )
    assert device.calls == [
        ("set_attribute", "brightness", 200),
        ("set_attribute", "color_temperature", 5000),
        ("set_attribute", "effect", "Cinema"),
    ]

    device.calls.clear()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_entry.entity_id},
        blocking=True,
    )
    assert device.calls == [("set_attribute", "power", False)]


async def test_light_turn_on_does_not_repower_when_already_on(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test turn_on with extra params does not resend power when already on."""
    device = _x13_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]

    device.calls.clear()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_entry.entity_id, ATTR_BRIGHTNESS: 50},
        blocking=True,
    )
    assert device.calls == [("set_attribute", "brightness", 50)]


async def test_light_turn_on_powers_on_when_off(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test turn_on powers the device on when currently off."""
    device = _x13_device()
    device.attributes[X13Attributes.power] = False
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]

    device.calls.clear()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_entry.entity_id},
        blocking=True,
    )
    assert device.calls == [("set_attribute", "power", True)]


async def test_light_brightness_only_color_mode(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test the light falls back to brightness-only mode without color_temperature."""
    device = DummyDevice(
        DeviceType.X13,
        attributes={
            X13Attributes.power: True,
            X13Attributes.brightness: 50,
            X13Attributes.color_temperature: None,
            X13Attributes.effect: None,
            X13Attributes.rgb_color: None,
        },
    )
    device.color_temp_range = [2700, 6500]
    device.effects = X13_EFFECTS
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert ATTR_EFFECT not in state.attributes


async def test_light_onoff_only_before_first_status(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test the light reports onoff-only and unknown state before any attribute is known."""
    device = DummyDevice(DeviceType.X13, attributes={})
    device.color_temp_range = [2700, 6500]
    device.effects = X13_EFFECTS
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "unknown"
    # Home Assistant only reports a color_mode while is_on is true;
    # with power unknown it reports None here even though a power-on onoff-only light
    # reports ColorMode.ONOFF.
    assert state.attributes[ATTR_COLOR_MODE] is None
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]


async def test_light_onoff_only_color_mode(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a powered-on light with no brightness/color_temperature reports ONOFF."""
    device = DummyDevice(
        DeviceType.X13,
        attributes={
            X13Attributes.power: True,
            X13Attributes.brightness: None,
            X13Attributes.color_temperature: None,
            X13Attributes.effect: None,
            X13Attributes.rgb_color: None,
        },
    )
    device.color_temp_range = [2700, 6500]
    device.effects = X13_EFFECTS
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "on"
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.ONOFF
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]


async def test_light_not_created_for_other_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no light entity is created for a device type without one."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_light_turn_on_raises_on_device_communication_error(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a device communication failure surfaces as a HomeAssistantError."""
    device = _x13_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]

    with (
        patch.object(device, "set_attribute", side_effect=SocketException("offline")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_entry.entity_id},
            blocking=True,
        )
