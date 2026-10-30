"""Test setting the KACO RS485 entry up, and what happens when it fails."""

from freezegun.api import FrozenDateTimeFactory
from kaco_rs485 import BusError
from kaco_rs485.testing import FakeBus
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.kaco_rs485.const import DOMAIN
from homeassistant.components.kaco_rs485.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


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


async def test_devices_are_named_from_the_setup_scan(
    device_registry: dr.DeviceRegistry, init_integration: MockConfigEntry
) -> None:
    """Test each inverter becomes a device named for what the scan recorded."""
    entry = init_integration

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry.entry_id}_1"), entry.entry_id
    )
    assert device is not None
    assert device.name == "KACO Powador 6400xi (1)"
    assert device.manufacturer == "KACO new energy"
    assert device.model == "6400xi"
    assert device.sw_version == "K222.36DE 6817"

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
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, bus: FakeBus
) -> set[int]:
    """Run one cycle and return the addresses it actually asked."""
    bus.requests.clear()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    return {address for address, _ in bus.requests}


async def test_a_disabled_inverter_is_dropped_from_the_poll_cycle(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_bus: FakeBus,
) -> None:
    """Test disabling an inverter stops it costing bus time, not just hiding it."""
    assert await _polled(hass, freezer, mock_bus) == {1, 2, 4}

    device_registry.async_update_device(
        _device(device_registry, init_integration, 2).id,
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    assert await _polled(hass, freezer, mock_bus) == {1, 4}


async def test_an_entry_with_every_inverter_disabled_does_not_open_the_port(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
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

    assert await _polled(hass, freezer, mock_bus) == set()
    assert not mock_bus.opened
