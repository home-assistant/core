"""Test setting the KACO Modbus entry up, and what happens when it fails."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from kaco_modbus import SunSpecMapShiftError
from kaco_modbus.testing import BLUEPLANET_86TL3, with_manufacturer
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.kaco_modbus.const import DOMAIN
from homeassistant.components.kaco_modbus.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED

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


@pytest.mark.usefixtures("mock_get_unit")
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

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    unit.fail_requests(None)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "register_image", [with_manufacturer(BLUEPLANET_86TL3, "Fronius")]
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_another_brand_at_the_same_address_fails_permanently(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a swapped device is a setup error, not an endless retry.

    Retrying cannot make a Fronius into a KACO, so this must not sit in
    SETUP_RETRY polling someone else's inverter forever.
    """
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


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
    with (
        patch(
            "homeassistant.components.kaco_modbus.KacoInverter.async_update_readings",
            side_effect=SunSpecMapShiftError("moved"),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    reload.assert_called_once_with(init_integration.entry_id)
