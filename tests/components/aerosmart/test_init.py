"""Tests for the aerosmart config-entry setup."""

import asyncio
from unittest.mock import patch

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusUnit

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import MockModbusApi

from tests.common import MockConfigEntry


async def test_setup_entry_keeps_retrying_after_background_connect_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """A connect failure leaves entities unavailable for a scheduled retry.

    The gateway between HA and the real device is a slow RS232-to-Modbus-TCP
    bridge that occasionally times out on connect. The device library's timing
    requirements must not permanently break the integration until
    someone manually reloads it.
    """
    mock_modbus_unit_ventilation.fail_requests(
        ModbusConnectionError("simulated read failure")
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.readings.last_update_success is False
    outside_temp = hass.states.get("sensor.aerosmart_temperatur_aussenluft")
    assert outside_temp is not None
    assert outside_temp.state == STATE_UNAVAILABLE


async def test_setup_entry_does_not_wait_for_initial_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The slow serial poll runs as a config-entry background task."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_refresh(_runtime: object) -> None:
        started.set()
        await release.wait()

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aerosmart._async_initial_refresh",
        side_effect=delayed_refresh,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await started.wait()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert not mock_config_entry.runtime_data.initial_refresh_task.done()
        outside_temp = hass.states.get("sensor.aerosmart_temperatur_aussenluft")
        assert outside_temp is not None
        assert outside_temp.state == STATE_UNAVAILABLE

        release.set()
        await mock_config_entry.runtime_data.async_wait_initial_refresh()


async def test_setup_entry_creates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_api: MockModbusApi,
) -> None:
    """The entry loads and produces entities across every platform."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_modbus_api.get_unit.call_count == 2

    wochentag = hass.states.get("sensor.aerosmart_wochentag")
    assert wochentag is not None
    assert wochentag.state == "3"

    outside_temp = hass.states.get("sensor.aerosmart_temperatur_aussenluft")
    assert outside_temp is not None
    assert outside_temp.state == "0.123"

    heat_pump_status = hass.states.get("sensor.aerosmart_status_warmepumpe")
    assert heat_pump_status is not None
    assert heat_pump_status.state == "Wärmepumpe aus"
    assert heat_pump_status.attributes["options"] == [
        "Wiedereinschaltsperre",
        "Wärmepumpe aus",
        "Vorlaufzeit Solepumpe",
        "Vorlaufzeit Ventilatoren",
        "Öffnen Heißgasventil",
        "Öffnen Flüssiggasventil",
        "Start Kompressor",
        "Mindestlaufzeit Wärmepumpe",
        "Wärmepumpe ein",
        "Kältemittel absaugen",
        "Beim Abtauen absaugen",
        "Abtauen ein",
        "Nach Abtauen abtropfen",
    ]


async def test_unload_releases_shared_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unloading lets Home Assistant release its shared connection holds."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_migrates_legacy_shared_connection_entry(hass: HomeAssistant) -> None:
    """Version 1 entries copy host and port from their former connection entry."""
    legacy_connection = MockConfigEntry(
        domain="modbus_connection",
        data={CONF_HOST: "gateway.local", CONF_PORT: 8899},
    )
    legacy_connection.add_to_hass(hass)
    entry = MockConfigEntry(
        domain="aerosmart",
        version=1,
        data={
            "connection_entry_id": legacy_connection.entry_id,
            "unit_ventilation": 1,
            "unit_heat_pump": 2,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await entry.runtime_data.async_wait_initial_refresh()
    assert entry.version == 2
    assert entry.unique_id == "gateway.local:8899_1_2"
    assert entry.data == {
        CONF_HOST: "gateway.local",
        CONF_PORT: 8899,
        "unit_ventilation": 1,
        "unit_heat_pump": 2,
    }
