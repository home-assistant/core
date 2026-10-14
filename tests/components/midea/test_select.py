"""Tests for midea select.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.a1 import DeviceAttributes as A1Attributes, MideaA1Device
from midealocal.devices.ac import DeviceAttributes as ACAttributes, MideaACDevice
from midealocal.devices.c3 import DeviceAttributes as C3Attributes, MideaC3Device
from midealocal.devices.cc import DeviceAttributes as CCAttributes
from midealocal.devices.fa import DeviceAttributes as FAAttributes, MideaFADevice
from midealocal.devices.fc import DeviceAttributes as FCAttributes, MideaFCDevice
from midealocal.devices.fd import DeviceAttributes as FDAttributes, MideaFDDevice
from midealocal.devices.x40 import DeviceAttributes as X40Attributes, MideaX40Device
from midealocal.exceptions import SocketException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, SetDeviceAttribute, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


async def _assert_service_call(
    hass: HomeAssistant,
    entity_id: str,
    option: str,
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call select.select_option and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )
    assert device.calls == expected_calls


def _x40_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.X40,
        attributes={X40Attributes.direction: "90"},
    )
    device.directions = list(MideaX40Device._directions)
    return device


def _a1_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.A1,
        attributes={
            A1Attributes.fan_speed: "medium",
            A1Attributes.water_level_set: "50",
        },
    )
    device.fan_speeds = list(MideaA1Device._default_speeds.values())
    device.water_level_sets = list(MideaA1Device._water_level_sets)
    return device


def _ac_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.wind_lr_angle: "off",
            ACAttributes.wind_ud_angle: "off",
            ACAttributes.rate_select: "100",
        },
    )
    device.wind_lr_angles = list(MideaACDevice._wind_lr_angles.values())
    device.wind_ud_angles = list(MideaACDevice._wind_ud_angles.values())
    device.rate_selects = list(MideaACDevice._rate_selects.values())
    return device


def _c3_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.C3,
        attributes={C3Attributes.silent_level: "off"},
    )
    device.silent_modes = list(MideaC3Device._silent_modes)
    return device


def _fa_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.FA,
        attributes={
            FAAttributes.oscillation_mode: "off",
            FAAttributes.oscillation_angle: "90",
            FAAttributes.tilting_angle: "off",
        },
    )
    device.oscillation_modes = list(MideaFADevice._oscillation_modes)
    device.oscillation_angles = list(MideaFADevice._oscillation_angles)
    device.tilting_angles = list(MideaFADevice._tilting_angles)
    return device


def _fc_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.FC,
        attributes={
            FCAttributes.detect_mode: "off",
            FCAttributes.mode: "auto",
            FCAttributes.fan_speed: "auto",
            FCAttributes.screen_display: "bright",
        },
    )
    device.detect_modes = list(MideaFCDevice._detect_modes)
    device.modes = list(MideaFCDevice._modes.values())
    device.fan_speeds = list(MideaFCDevice._speeds.values())
    device.screen_displays = list(MideaFCDevice._screen_displays.values())
    return device


def _fd_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.FD,
        attributes={
            FDAttributes.fan_speed: "auto",
            FDAttributes.screen_display: "bright",
        },
    )
    device.fan_speeds = list(MideaFDDevice._speeds_old.values())
    device.screen_displays = list(MideaFDDevice._screen_displays.values())
    return device


ALL_SELECT_DEVICES = [
    pytest.param(_x40_device(), id="x40"),
    pytest.param(_a1_device(), id="a1"),
    pytest.param(_ac_device(), id="ac"),
    pytest.param(_c3_device(), id="c3"),
    pytest.param(_fa_device(), id="fa"),
    pytest.param(_fc_device(), id="fc"),
    pytest.param(_fd_device(), id="fd"),
]


@pytest.mark.parametrize("device", ALL_SELECT_DEVICES)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device: DummyDevice,
) -> None:
    """Test async_setup_entry creates the right select entities per device type."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_x40_direction_select(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test X40's direction select reflects state and can be changed."""
    device = _x40_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_direction"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "90"
    assert state.attributes[ATTR_OPTIONS] == device.directions

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        "oscillate",
        [("set_attribute", "direction", "oscillate")],
        device,
    )


async def test_ac_angle_and_rate_selects(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test AC's wind angle and rate selects."""
    device = _ac_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    entities = entity_entries(hass, config_entry)
    assert f"{TEST_DEVICE_ID}_wind_lr_angle" in entities
    assert f"{TEST_DEVICE_ID}_wind_ud_angle" in entities
    assert f"{TEST_DEVICE_ID}_rate_select" in entities

    await _assert_service_call(
        hass,
        entities[f"{TEST_DEVICE_ID}_wind_lr_angle"].entity_id,
        "left",
        [("set_attribute", "wind_lr_angle", "left")],
        device,
    )
    await _assert_service_call(
        hass,
        entities[f"{TEST_DEVICE_ID}_rate_select"].entity_id,
        "20",
        [("set_attribute", "rate_select", "20")],
        device,
    )


@pytest.mark.parametrize(
    "unique_id",
    [
        f"{TEST_DEVICE_ID}_wind_lr_angle",
        f"{TEST_DEVICE_ID}_wind_ud_angle",
        f"{TEST_DEVICE_ID}_rate_select",
    ],
)
async def test_ac_selects_unavailable_when_power_off(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    set_device_attribute: SetDeviceAttribute,
    unique_id: str,
) -> None:
    """Test AC angle/rate selects are unavailable while the unit is powered off."""
    device = _ac_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    entity_id = entity_entries(hass, config_entry)[unique_id].entity_id
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state != STATE_UNAVAILABLE

    await set_device_attribute(device, ACAttributes.power, False)
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_UNAVAILABLE

    await set_device_attribute(device, ACAttributes.power, True)
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state != STATE_UNAVAILABLE

    device.available = False
    device.notify_update({"available": False})
    await hass.async_block_till_done()
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_UNAVAILABLE


async def test_fa_selects_do_not_overlap_fan_platform(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test FA exposes oscillation_mode/angle and tilting_angle selects."""
    device = _fa_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    entities = entity_entries(hass, config_entry)
    assert f"{TEST_DEVICE_ID}_oscillation_mode" in entities
    assert f"{TEST_DEVICE_ID}_oscillation_angle" in entities
    assert f"{TEST_DEVICE_ID}_tilting_angle" in entities

    await _assert_service_call(
        hass,
        entities[f"{TEST_DEVICE_ID}_oscillation_mode"].entity_id,
        "oscillation",
        [("set_attribute", "oscillation_mode", "oscillation")],
        device,
    )


async def test_fc_selects(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test FC exposes detect_mode, mode, fan_speed and screen_display selects."""
    device = _fc_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    entities = entity_entries(hass, config_entry)
    assert f"{TEST_DEVICE_ID}_detect_mode" in entities
    assert f"{TEST_DEVICE_ID}_mode" in entities
    assert f"{TEST_DEVICE_ID}_fan_speed" in entities
    assert f"{TEST_DEVICE_ID}_screen_display" in entities

    await _assert_service_call(
        hass,
        entities[f"{TEST_DEVICE_ID}_screen_display"].entity_id,
        "dim",
        [("set_attribute", "screen_display", "dim")],
        device,
    )


async def test_select_unknown_when_attribute_becomes_non_str(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test current_option gracefully reports unknown if a later update clears it."""
    device = _x40_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_direction"]
    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "90"

    device.attributes[X40Attributes.direction] = None
    device.notify_update({X40Attributes.direction: None})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "unknown"


async def test_select_not_created_when_attribute_missing(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no select entity is created when the device does not report the attribute."""
    device = DummyDevice(DeviceType.X40, attributes={})
    device.directions = ["60", "70", "80", "90", "100", "oscillate"]
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_select_not_created_for_other_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no select entity is created for a device type without one (e.g. CC)."""
    device = DummyDevice(
        DeviceType.CC,
        attributes={
            CCAttributes.power: True,
            CCAttributes.mode: 1,
            CCAttributes.fan_speed: "high",
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_select_option_raises_on_device_communication_error(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a device communication failure surfaces as a HomeAssistantError."""
    device = _x40_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_direction"]

    with (
        patch.object(device, "set_attribute", side_effect=SocketException("offline")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_entry.entity_id, ATTR_OPTION: "60"},
            blocking=True,
        )
