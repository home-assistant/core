"""Tests for the Lunatone integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from lunatone_rest_api_client import Device
from lunatone_rest_api_client.models import ControlData
import pytest

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.components.lunatone.light import LunatoneLight
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import DEVICE_DATA_LIST, SERIAL_NUMBER, setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def mock_lunatone_device(mock_lunatone_auth: AsyncMock) -> Device:
    """Mock a Lunatone device object."""
    device = Device(mock_lunatone_auth, DEVICE_DATA_LIST[0])
    device.async_update = AsyncMock()
    device.async_control = AsyncMock()
    return device


@pytest.fixture
def mock_lunatone_devices_coordinator(
    mock_lunatone_devices: AsyncMock,
) -> Generator[AsyncMock]:
    """Mock a Lunatone devices coordinator object."""
    with (
        patch(
            "homeassistant.components.lunatone.LunatoneDevicesDataUpdateCoordinator",
            autospec=True,
        ) as mock_coordinator,
        patch(
            "homeassistant.components.lunatone.light.LunatoneDevicesDataUpdateCoordinator",
            new=mock_coordinator,
        ),
    ):
        coordinator = mock_coordinator.return_value
        coordinator.devices_api = mock_lunatone_devices
        coordinator.device_api_mapping = {
            device.id: device for device in mock_lunatone_devices.devices
        }
        coordinator.last_update_success = True
        yield coordinator


@pytest.fixture
def light_entity(
    mock_lunatone_devices_coordinator: AsyncMock, mock_lunatone_device: Device
) -> LunatoneLight:
    """Create a LunatoneLight entity using the mock device."""

    async def fake_control(control_data: ControlData):
        if control_data.switchable is not None:
            mock_lunatone_device._data.features.switchable.status = (
                control_data.switchable
            )

    mock_lunatone_device.async_control.side_effect = fake_control

    entity = LunatoneLight(
        mock_lunatone_devices_coordinator, mock_lunatone_device.id, SERIAL_NUMBER
    )
    entity._device = mock_lunatone_device
    entity.async_write_ha_state = MagicMock()
    return entity


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    for device_data in DEVICE_DATA_LIST:
        expected_unique_id = f"{SERIAL_NUMBER}-device{device_data.id}"

        entry = entity_registry.async_get(f"light.device_{device_data.id}")
        assert entry
        assert entry.device_id
        assert entry.unique_id == expected_unique_id

        device_entry = device_registry.async_get(entry.device_id)
        assert device_entry
        assert device_entry.identifiers == {(DOMAIN, expected_unique_id)}
        assert device_entry.name == f"Device {device_data.id}"


async def test_turn_on_off(light_entity: LunatoneLight) -> None:
    """Test the light can be turned off."""
    await light_entity.async_turn_on()
    assert light_entity.is_on

    await light_entity.async_turn_off()
    assert not light_entity.is_on

    assert light_entity._device.async_control.call_count == 2


async def test_turn_on_off_not_doing_anything_because_device_is_none(
    light_entity: LunatoneLight,
) -> None:
    """Test the light cannot be controlled."""
    light_entity._device = None

    await light_entity.async_turn_on()
    assert not light_entity.is_on

    await light_entity.async_turn_off()
    assert not light_entity.is_on


async def test_coordinator_update_handling(light_entity: LunatoneLight) -> None:
    """Test the coordinator update handling."""
    light_entity.coordinator.devices_api.data.devices[
        0
    ].features.switchable.status = True
    light_entity._handle_coordinator_update()
    assert (
        light_entity._device.data
        == light_entity.coordinator.devices_api.data.devices[0]
    )

    light_entity.coordinator.devices_api.data.devices[
        0
    ].features.switchable.status = False
    light_entity._handle_coordinator_update()
    assert (
        light_entity._device.data
        == light_entity.coordinator.devices_api.data.devices[0]
    )
