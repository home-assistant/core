"""Tests for midea humidifier.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.a1 import DeviceAttributes as A1Attributes, MideaA1Device
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.fd import DeviceAttributes as FDAttributes, MideaFDDevice
from midealocal.exceptions import SocketException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.humidifier import (
    ATTR_AVAILABLE_MODES,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.midea.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


async def _assert_service_call(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    service_data: dict,
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call a humidifier service and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )
    assert device.calls == expected_calls


def _a1_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.A1,
        attributes={
            A1Attributes.power: True,
            A1Attributes.mode: "auto",
            A1Attributes.target_humidity: 55,
            A1Attributes.current_humidity: 60,
        },
    )
    device.modes = list(MideaA1Device._default_modes.values())
    return device


def _fd_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.FD,
        attributes={
            FDAttributes.power: True,
            FDAttributes.mode: "continuous",
            FDAttributes.target_humidity: 45,
            FDAttributes.current_humidity: 40,
        },
    )
    device.modes = list(MideaFDDevice._modes)
    return device


@pytest.mark.parametrize(
    "device",
    [
        pytest.param(_a1_device(), id="a1"),
        pytest.param(_fd_device(), id="fd"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_humidifier_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device: DummyDevice,
) -> None:
    """Test async_setup_entry creates the right humidifier entity per device type."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.HUMIDIFIER]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("device", "expected_model"),
    [
        pytest.param(_a1_device(), "Dehumidifier", id="a1"),
        pytest.param(_fd_device(), "Humidifier", id="fd"),
    ],
)
async def test_humidifier_device_info_model(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    device: DummyDevice,
    expected_model: str,
) -> None:
    """Test the device registry entry uses the right model name for A1 and FD."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.HUMIDIFIER]):
        await setup_integration(hass, config_entry, device)

    assert (
        device_entry := device_registry.async_get_device_by_identifier(
            (DOMAIN, str(TEST_DEVICE_ID)), config_entry.entry_id
        )
    ) is not None
    assert device_entry.model == expected_model


async def test_a1_humidifier_services(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test A1 humidifier service calls reach the device."""
    device = _a1_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.HUMIDIFIER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_humidifier"]

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "on"
    assert state.attributes[ATTR_HUMIDITY] == 55
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 60
    assert state.attributes[ATTR_MODE] == "auto"
    assert state.attributes[ATTR_AVAILABLE_MODES] == device.modes

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_HUMIDITY,
        {ATTR_HUMIDITY: 65},
        [("set_attribute", "target_humidity", 65)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_MODE,
        {ATTR_MODE: "continuous"},
        [("set_attribute", "mode", "continuous")],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_OFF,
        {},
        [("set_attribute", "power", False)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {},
        [("set_attribute", "power", True)],
        device,
    )


async def test_humidifier_not_created_for_other_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no humidifier entity is created for a device type without one."""
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
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.HUMIDIFIER]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_humidifier_unknown_mode_and_power_return_none(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test mode and is_on gracefully report unknown when attributes are unset."""
    device = DummyDevice(
        DeviceType.A1,
        attributes={
            A1Attributes.power: None,
            A1Attributes.mode: None,
            A1Attributes.target_humidity: None,
            A1Attributes.current_humidity: None,
        },
    )
    device.modes = ["Manual", "Continuous", "Auto"]
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.HUMIDIFIER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_humidifier"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "unknown"
    assert state.attributes.get(ATTR_HUMIDITY) is None
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) is None
    assert state.attributes.get(ATTR_MODE) is None


async def test_humidifier_turn_on_raises_on_device_communication_error(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a device communication failure surfaces as a HomeAssistantError."""
    device = _fd_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.HUMIDIFIER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_humidifier"]

    with (
        patch.object(device, "set_attribute", side_effect=SocketException("offline")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_entry.entity_id},
            blocking=True,
        )
