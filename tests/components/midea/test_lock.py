"""Tests for midea lock.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.exceptions import SocketException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform

LOCK_DEVICE_TYPES = [
    DeviceType.X34,
    DeviceType.A1,
    DeviceType.C2,
    DeviceType.CE,
    DeviceType.E1,
    DeviceType.ED,
    DeviceType.FA,
    DeviceType.FB,
    DeviceType.FC,
]


async def _assert_service_call(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call a lock service and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        LOCK_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert device.calls == expected_calls


@pytest.mark.parametrize("device_type", LOCK_DEVICE_TYPES)
async def test_lock_created_and_state_for_each_supported_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    device_type: DeviceType,
) -> None:
    """Test the child lock entity is created and reflects state for every supported type."""
    device = DummyDevice(device_type, attributes={"child_lock": True})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_child_lock"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "locked"

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_UNLOCK,
        [("set_attribute", "child_lock", False)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_LOCK,
        [("set_attribute", "child_lock", True)],
        device,
    )


@pytest.mark.parametrize(
    "device_type",
    [DeviceType.C2, DeviceType.FB],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lock_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_type: DeviceType,
) -> None:
    """Test the child lock entity registry entry and state."""
    device = DummyDevice(device_type, attributes={"child_lock": False})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_lock_unknown_when_attribute_becomes_non_bool(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test is_locked gracefully reports unknown if a later update clears the value."""
    device = DummyDevice(DeviceType.C2, attributes={"child_lock": True})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_child_lock"]
    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "locked"

    device.attributes["child_lock"] = None
    device.notify_update({"child_lock": None})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "unknown"


async def test_lock_not_created_when_attribute_missing(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no lock entity is created when the device does not report child_lock."""
    device = DummyDevice(DeviceType.C2, attributes={})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_lock_not_created_for_other_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no lock entity is created for a device type without one."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            # AC has no "child_lock" attribute, but even a stray one under
            # this key should not create a lock entity since AC is not in
            # the description's models.
            "child_lock": True,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_lock_raises_on_device_communication_error(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a device communication failure surfaces as a HomeAssistantError."""
    device = DummyDevice(DeviceType.C2, attributes={"child_lock": False})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_child_lock"]

    with (
        patch.object(device, "set_attribute", side_effect=SocketException("offline")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: entity_entry.entity_id},
            blocking=True,
        )
