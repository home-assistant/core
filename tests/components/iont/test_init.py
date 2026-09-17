"""Tests for the IONT config-entry setup."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    ModbusConnectionError,
    ModbusTimeoutError,
    ServerDeviceFailureError,
)
from modbus_connection.encode import encode_int
from modbus_connection.mock import MockModbusUnit
import pytest

from homeassistant.components.iont.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import (
    CONNECTOR_COUNT_REGISTER,
    MOCK_HOST,
    MOCK_TITLE,
    connector_base,
    seed_dc_charger,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed

POWER_ENTITY = "sensor.connector_1_power"
SECOND_POWER_ENTITY = "sensor.connector_2_power"


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_load_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The entry loads, produces entities, and unloads cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == "7150"

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A charger that does not answer puts the entry in retry."""
    mock_modbus_unit.fail_requests(ModbusTimeoutError("timed out"))

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_error_when_not_a_charger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A device that answers but is not an IONT charger fails setup for good."""
    mock_modbus_unit.input[CONNECTOR_COUNT_REGISTER] = encode_int(0, count=2)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_error_when_link_settings_in_use(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A device already held over other link settings fails setup for good."""
    with patch(
        "homeassistant.components.iont.async_get_unit",
        side_effect=HomeAssistantError("in use"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """The charger is a device, with each connector a sub-device of it."""
    charger = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id), init_integration.entry_id
    )
    assert charger is not None
    assert charger.name == MOCK_TITLE
    assert charger.manufacturer == "IONT"
    assert charger.configuration_url == f"http://{MOCK_HOST}"

    connector = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{init_integration.entry_id}_connector_1"),
        init_integration.entry_id,
    )
    assert connector is not None
    assert connector.via_device_id == charger.id
    assert connector.name == "Connector 1"
    assert connector.manufacturer == "IONT"


async def test_connector_that_left_the_charger_is_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A connector the charger stops reporting does not linger as a device."""
    seed_dc_charger(mock_modbus_unit)
    await setup_integration(hass, mock_config_entry)

    second = (DOMAIN, f"{mock_config_entry.entry_id}_connector_2")
    assert (
        device_registry.async_get_device_by_identifier(
            second, mock_config_entry.entry_id
        )
        is not None
    )

    mock_modbus_unit.input[CONNECTOR_COUNT_REGISTER] = encode_int(1, count=2)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            second, mock_config_entry.entry_id
        )
        is None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{mock_config_entry.entry_id}_connector_1"),
            mock_config_entry.entry_id,
        )
        is not None
    )


async def test_dead_link_fails_the_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """A charger that answers nothing marks the entities unavailable, then recovers."""
    mock_modbus_unit.fail_requests(ModbusConnectionError("link died"))

    await _tick(hass, freezer)

    assert init_integration.runtime_data.last_update_success is False
    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_modbus_unit.fail_requests(None)

    await _tick(hass, freezer)

    state = hass.states.get(POWER_ENTITY)
    assert state is not None
    assert state.state == "7150"


async def test_silent_connector_leaves_the_others_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One connector that stops answering only takes its own entities down."""
    seed_dc_charger(mock_modbus_unit)
    await setup_integration(hass, mock_config_entry)

    mock_modbus_unit.fail_read(
        connector_base(2), ServerDeviceFailureError(), register_type="input"
    )

    await _tick(hass, freezer)
    await _tick(hass, freezer)

    assert hass.states.get(SECOND_POWER_ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get(POWER_ENTITY).state == "7150"
    assert hass.states.get("sensor.iont_charger_available_power").state == "7360"
    # Logged once, not on every poll.
    assert caplog.text.count("connector_2 did not answer this poll") == 1

    mock_modbus_unit.fail_read(connector_base(2), None, register_type="input")

    await _tick(hass, freezer)

    assert hass.states.get(SECOND_POWER_ENTITY).state == "0"
    assert "connector_2 is answering again" in caplog.text
