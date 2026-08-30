"""Test setting the KACO Modbus entry up, and what happens when it fails."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from kaco_modbus import SunSpecMapShiftError
from kaco_modbus.testing import BLUEPLANET_86TL3, with_manufacturer
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection

from homeassistant.components.kaco_modbus.const import DOMAIN
from homeassistant.components.kaco_modbus.coordinator import (
    SCAN_INTERVAL,
    KacoDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_SERIAL, MOCK_USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed


def _patch_get_unit(connection: MockModbusConnection) -> object:
    """Hand the integration a unit on *connection* instead of a real one."""
    return patch(
        "homeassistant.components.kaco_modbus.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    )


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads with runtime_data populated."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert isinstance(init_integration.runtime_data, KacoDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_device_registry_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the inverter is identified by serial, which survives a move."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), init_integration.entry_id
    )

    assert device is not None
    assert device.manufacturer == "KACO new energy"
    assert device.model == "blueplanet 8.6 TL3 INT"
    assert device.sw_version == "V5.53"
    assert device.serial_number == MOCK_SERIAL


async def test_a_silent_inverter_retries_and_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an inverter asleep at setup is retried rather than given up on."""
    mock_config_entry.add_to_hass(hass)
    unit = mock_connection.for_unit(1)
    unit.fail_requests(ModbusTimeoutError("asleep"))

    with _patch_get_unit(mock_connection):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        unit.fail_requests(None)
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_another_brand_at_the_same_address_fails_permanently(
    hass: HomeAssistant,
) -> None:
    """Test a swapped device is a setup error, not an endless retry.

    Retrying cannot make a Fronius into a KACO, so this must not sit in
    SETUP_RETRY polling someone else's inverter forever.
    """
    connection = MockModbusConnection()
    connection.for_unit(1).load_raw(
        {"holding": with_manufacturer(BLUEPLANET_86TL3, "Fronius")}
    )
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    with _patch_get_unit(connection):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_a_moved_sunspec_map_reloads_the_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
) -> None:
    """Test a shifted model chain triggers rediscovery.

    Every bound register offset is stale, so polling on would report
    plausible nonsense rather than fail. SunSpecMapShiftError is not a
    ModbusError, so it needs handling of its own.
    """
    device = init_integration.runtime_data.device

    with (
        patch.object(
            device, "async_update_readings", side_effect=SunSpecMapShiftError("moved")
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    reload.assert_called_once_with(init_integration.entry_id)
