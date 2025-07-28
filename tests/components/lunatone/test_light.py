"""Tests for the Lunatone integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import aiohttp
from awesomeversion import AwesomeVersion
from lunatone_rest_api_client import Device
from lunatone_rest_api_client.models import ControlData, DeviceData, DevicesData
import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.components.lunatone.light import LunatoneLight
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

DEVICE_DATA: list[DeviceData] = [
    DeviceData(id=1, name="Device 1"),
    DeviceData(id=2, name="Device 2"),
]
DEVICES_DATA = DevicesData(devices=DEVICE_DATA)


@pytest.fixture
def mock_lunatone_device(mock_lunatone_auth: AsyncMock) -> Generator[AsyncMock]:
    """Mock a Lunatone device object."""
    device = AsyncMock(spec=Device)
    device._auth = mock_lunatone_auth
    device.id = DEVICE_DATA[0].id
    device.name = DEVICE_DATA[0].name
    device.data = DEVICE_DATA[0]
    return device


@pytest.fixture
def mock_lunatone_device_list(mock_lunatone_auth: AsyncMock) -> Generator[AsyncMock]:
    """Mock a Lunatone device object list."""
    devices: list[Device] = []
    for device_data in DEVICE_DATA:
        device = AsyncMock(spec=Device)
        device._auth = mock_lunatone_auth
        device.id = device_data.id
        device.name = device_data.name
        device.data = device_data
        devices.append(device)
    return devices


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_device_list: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    mock_lunatone_devices.devices = mock_lunatone_device_list

    mock_config_entry.add_to_hass(hass)
    with patch("asyncio.sleep"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for i, _ in enumerate(DEVICE_DATA, start=1):
        expected_unique_id = f"12345-device{i}"

        entry = entity_registry.async_get(f"light.device_{i}")
        assert entry
        assert entry.device_id
        assert entry.unique_id == expected_unique_id

        device_entry = device_registry.async_get(entry.device_id)
        assert device_entry
        assert device_entry.identifiers == {(DOMAIN, expected_unique_id)}
        assert device_entry.name == f"Device {i}"


async def test_switch_off(
    hass: HomeAssistant,
    mock_lunatone_device_list: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light can be turned off."""
    mock_lunatone_devices.devices = mock_lunatone_device_list

    mock_config_entry.add_to_hass(hass)
    with patch("asyncio.sleep"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.device_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lunatone_devices.devices[0].async_control.assert_called_once_with(
        ControlData(switchable=False)
    )


async def test_switch_on(
    hass: HomeAssistant,
    mock_lunatone_device_list: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light can be turned off."""
    mock_lunatone_devices.devices = mock_lunatone_device_list

    mock_config_entry.add_to_hass(hass)
    with patch("asyncio.sleep"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.device_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_lunatone_devices.devices[0].async_control.assert_called_once_with(
        ControlData(switchable=True)
    )


async def test_availability_on_error(
    hass: HomeAssistant,
    mock_lunatone_device: AsyncMock,
) -> None:
    """Test the availability on error."""
    version = AwesomeVersion("1.14.1")
    entity = LunatoneLight(mock_lunatone_device, 12345, version)

    # Simuliere Fehler → Unavailable
    mock_lunatone_device.async_update.side_effect = aiohttp.ClientConnectionError()
    await entity.async_update()
    assert not entity.available

    # Simuliere Erfolg → Wieder verfügbar
    mock_lunatone_device.async_update.side_effect = None
    await entity.async_update()
    assert entity.available
