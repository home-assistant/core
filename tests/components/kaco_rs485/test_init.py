"""Test setting the KACO RS485 entry up, and what happens when it fails."""

from freezegun.api import FrozenDateTimeFactory
from kaco_rs485 import BusError
from kaco_rs485.testing import FakeBus
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from homeassistant.components.kaco_rs485.const import (
    CONF_ADDRESSES,
    CONF_INVERTERS,
    DOMAIN,
)
from homeassistant.components.kaco_rs485.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import CYCLES_UNTIL_DARK, run_cycles


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


@pytest.fixture
def silenced() -> tuple[int, ...]:
    """Addresses that have stopped answering; tests override this."""
    return ()


@pytest.fixture
async def dark_inverters(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
    silenced: tuple[int, ...],
) -> None:
    """Let the silenced inverters go dark."""
    assert mock_bus.opened
    mock_bus.silence(*silenced)
    await run_cycles(hass, freezer, CYCLES_UNTIL_DARK)


@pytest.fixture
async def ws_client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, dark_inverters: None
) -> MockHAClientWebSocket:
    """A websocket client that can remove devices.

    Connects after the cycles have run: the jump in time would drop it.
    """
    assert await async_setup_component(hass, "config", {})
    return await hass_ws_client(hass)


@pytest.mark.parametrize("silenced", [(2,)])
async def test_a_removed_inverter_is_no_longer_polled(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_bus: FakeBus,
    ws_client: MockHAClientWebSocket,
) -> None:
    """Test deleting a dark inverter's device drops it from the entry and the bus."""
    device = _device(device_registry, init_integration, 2)

    response = await ws_client.remove_device(device.id)

    assert response["success"]
    assert device_registry.async_get(device.id) is None
    assert init_integration.data[CONF_ADDRESSES] == [1, 4]
    assert "2" not in init_integration.data[CONF_INVERTERS]
    assert await _polled(hass, freezer, mock_bus) == {1, 4}


@pytest.mark.parametrize("silenced", [(1, 2, 4)])
async def test_removing_every_inverter_releases_the_port(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_bus: FakeBus,
    ws_client: MockHAClientWebSocket,
) -> None:
    """Test an entry left with no inverters stops holding the bus."""
    for address in (1, 2, 4):
        device = _device(device_registry, init_integration, address)
        assert (await ws_client.remove_device(device.id))["success"]
    await hass.async_block_till_done()

    assert init_integration.data[CONF_ADDRESSES] == []
    assert not mock_bus.opened
    assert await _polled(hass, freezer, mock_bus) == set()
    assert init_integration.state is ConfigEntryState.LOADED


async def test_an_answering_inverter_is_not_removed(
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    ws_client: MockHAClientWebSocket,
) -> None:
    """Test an inverter that still answers cannot be deleted; it is not gone."""
    device = _device(device_registry, init_integration, 2)

    response = await ws_client.remove_device(device.id)

    assert not response["success"]
    assert device_registry.async_get(device.id) is not None
    assert init_integration.data[CONF_ADDRESSES] == [1, 2, 4]


async def test_a_device_of_no_configured_inverter_can_be_deleted(
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    ws_client: MockHAClientWebSocket,
) -> None:
    """Test a leftover device is deleted without touching the polled inverters."""
    device = device_registry.async_get_or_create(
        config_entry_id=init_integration.entry_id,
        identifiers={(DOMAIN, f"{init_integration.entry_id}_7")},
    )

    response = await ws_client.remove_device(device.id)

    assert response["success"]
    assert init_integration.data[CONF_ADDRESSES] == [1, 2, 4]


async def test_setup_drops_devices_for_addresses_no_longer_configured(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup removes the device of an inverter the entry no longer lists."""
    stale = _device(device_registry, init_integration, 2)

    hass.config_entries.async_update_entry(
        init_integration,
        data={**init_integration.data, CONF_ADDRESSES: [1, 4]},
    )
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(stale.id) is None
    assert _device(device_registry, init_integration, 1)
    assert _device(device_registry, init_integration, 4)
