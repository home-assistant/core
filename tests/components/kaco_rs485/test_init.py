"""Test setting the KACO RS485 entry up, and what happens when it fails."""

from kaco_rs485 import BusError
from kaco_rs485.testing import FakeBus
import pytest

from homeassistant.components.kaco_rs485.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_unload_closes_the_bus(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test the port is released when the entry unloads."""
    assert mock_bus.opened

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert not mock_bus.opened


async def test_a_bus_that_cannot_be_opened_is_retried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test a port that will not open leaves the entry retrying, not failed."""
    mock_bus.open_error = BusError("could not open /dev/ttyUSB0")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_failed_setup_leaves_no_open_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test a failed setup releases the port; two masters corrupt the bus."""
    mock_bus.request_error = BusError("connection closed")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not mock_bus.opened


@pytest.mark.usefixtures("init_integration")
async def test_devices_are_named_from_the_setup_scan(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test each inverter becomes a device named for what the scan recorded."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_1"), entry.entry_id
    )
    assert device is not None
    assert device.name == "KACO Powador 6400xi (1)"
    assert device.manufacturer == "KACO new energy"
    assert device.model == "6400xi"
    assert device.sw_version == "K222.36DE 6817"
    # No serial number exists, so the address is the only distinguisher.
    assert device.serial_number is None

    other = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_4"), entry.entry_id
    )
    assert other is not None
    assert other.name == "KACO Powador 8000xi (4)"


def _device(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry, address: int
) -> dr.DeviceEntry:
    """Return one inverter's device."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_{address}"), entry.entry_id
    )
    assert device is not None
    return device


async def _polled(
    hass: HomeAssistant, entry: MockConfigEntry, bus: FakeBus
) -> set[int]:
    """Run one cycle and return the addresses it actually asked."""
    bus.requests.clear()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    return {address for address, _ in bus.requests}


async def test_a_disabled_inverter_is_dropped_from_the_poll_cycle(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_bus: FakeBus,
) -> None:
    """Test disabling an inverter stops it costing bus time, not just hiding it."""
    assert await _polled(hass, init_integration, mock_bus) == {1, 2, 4}

    device_registry.async_update_device(
        _device(device_registry, init_integration, 2).id,
        disabled_by=dr.DeviceEntryDisabler.USER,
    )
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert await _polled(hass, init_integration, mock_bus) == {1, 4}


async def test_disabling_every_inverter_releases_the_port(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_bus: FakeBus,
) -> None:
    """Test an entry with nothing to poll does not sit on the bus."""
    for address in (1, 2, 4):
        device_registry.async_update_device(
            _device(device_registry, init_integration, address).id,
            disabled_by=dr.DeviceEntryDisabler.USER,
        )
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert await _polled(hass, init_integration, mock_bus) == set()
    assert not mock_bus.opened
