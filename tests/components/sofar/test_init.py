"""Test the Sofar Inverter Modbus integration setup and unload."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusConnectionError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection

from homeassistant.components.sofar.const import DOMAIN
from homeassistant.components.sofar.coordinator import SofarRuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a config entry sets up and unloads with runtime_data populated."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, SofarRuntimeData)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_unrecognized_inverter_raises_setup_error(
    hass: HomeAssistant,
) -> None:
    """Test setup fails permanently (no retry) for an unrecognized serial."""
    # Not reachable via the config flow; covers an existing entry
    # outliving a sofar-modbus library downgrade. Caught before any
    # Modbus I/O, so no connection needs mocking here.
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="UNRECOGNIZED_SERIAL_XYZ", data=MOCK_USER_INPUT
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_unreachable_link_retries_and_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a dead link on first refresh retries setup, then recovers."""
    mock_config_entry.add_to_hass(hass)
    unit = mock_connection.for_unit(1)
    unit.fail_requests(ModbusTimeoutError("stuck"))

    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        unit.fail_requests(None)
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_settings_failure_does_not_block_reading_sensors(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a settings-block failure still lets reading sensors set up."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sofar.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
                unit_id
            ),
        ),
        patch(
            "sofar_modbus.modern.device.SofarInverter.async_update_settings",
            side_effect=ModbusConnectionError("settings unreachable"),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids("sensor")


async def test_sensor_platform_is_forwarded(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the sensor platform is set up as part of config entry setup."""
    assert hass.states.async_entity_ids("sensor")
