"""Tests for midea light.py."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.x13 import DeviceAttributes as X13Attributes, Midea13Device
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
    EFFECT_OFF,
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

X13_EFFECTS = list(Midea13Device._effects)


def _x13_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.X13,
        attributes={
            X13Attributes.power: True,
            X13Attributes.brightness: 128,
            X13Attributes.color_temperature: 4000,
            X13Attributes.effect: "none",
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
    assert state.attributes[ATTR_EFFECT] == EFFECT_OFF
    assert state.attributes[ATTR_EFFECT_LIST] == [
        EFFECT_OFF,
        *(effect for effect in X13_EFFECTS if effect != "none"),
    ]
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
            ATTR_EFFECT: "cinema",
        },
        blocking=True,
    )
    assert device.calls == [
        ("set_attribute", "brightness", 200),
        ("set_attribute", "color_temperature", 5000),
        ("set_attribute", "effect", "cinema"),
    ]

    device.calls.clear()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_entry.entity_id, ATTR_EFFECT: EFFECT_OFF},
        blocking=True,
    )
    assert device.calls == [("set_attribute", "effect", "none")]

    device.calls.clear()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_entry.entity_id},
        blocking=True,
    )
    assert device.calls == [("set_attribute", "power", False)]


@pytest.mark.parametrize(
    ("initial_power", "service_data", "expected_calls"),
    [
        pytest.param(
            True,
            {ATTR_BRIGHTNESS: 50},
            [("set_attribute", "brightness", 50)],
            id="already_on_skips_repower",
        ),
        pytest.param(
            False,
            {},
            [("set_attribute", "power", True)],
            id="off_powers_on",
        ),
    ],
)
async def test_light_turn_on_power_handling(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    initial_power: bool,
    service_data: dict[str, Any],
    expected_calls: list[tuple],
) -> None:
    """Test turn_on only resends power when the device is currently off."""
    device = _x13_device()
    device.attributes[X13Attributes.power] = initial_power
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]

    device.calls.clear()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_entry.entity_id, **service_data},
        blocking=True,
    )
    assert device.calls == expected_calls


@pytest.mark.parametrize(
    (
        "attributes",
        "expected_state",
        "expected_color_mode",
        "expected_supported_color_modes",
        "expected_has_effect",
    ),
    [
        pytest.param(
            {},
            "unknown",
            # HA only reports a color_mode while is_on is True.
            None,
            [ColorMode.ONOFF],
            False,
            id="before_first_status",
        ),
        pytest.param(
            {
                X13Attributes.power: True,
                X13Attributes.brightness: None,
                X13Attributes.color_temperature: None,
                X13Attributes.effect: None,
                X13Attributes.rgb_color: None,
            },
            "on",
            ColorMode.ONOFF,
            [ColorMode.ONOFF],
            False,
            id="onoff_only",
        ),
        pytest.param(
            {
                X13Attributes.power: True,
                X13Attributes.brightness: 50,
                X13Attributes.color_temperature: None,
                X13Attributes.effect: None,
                X13Attributes.rgb_color: None,
            },
            "on",
            ColorMode.BRIGHTNESS,
            [ColorMode.BRIGHTNESS],
            False,
            id="brightness_only",
        ),
    ],
)
async def test_light_color_mode_fallbacks(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    attributes: dict[X13Attributes, Any],
    expected_state: str,
    expected_color_mode: ColorMode | None,
    expected_supported_color_modes: list[ColorMode],
    expected_has_effect: bool,
) -> None:
    """Test the light falls back to the correct color mode based on reported capability."""
    device = DummyDevice(DeviceType.X13, attributes=attributes)
    device.color_temp_range = [2700, 6500]
    device.effects = X13_EFFECTS
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == expected_state
    assert state.attributes[ATTR_COLOR_MODE] == expected_color_mode
    assert (
        state.attributes[ATTR_SUPPORTED_COLOR_MODES] == expected_supported_color_modes
    )
    assert (ATTR_EFFECT in state.attributes) == expected_has_effect


async def test_light_effect_none_when_device_reports_non_string(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test effect is reported as None when the device value is not a string."""
    device = _x13_device()
    device.attributes[X13Attributes.effect] = 0
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_light"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.attributes[ATTR_EFFECT] is None


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
