"""Test for System Monitor init."""

from __future__ import annotations

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.systemmonitor.const import CONF_PROCESS, DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant, mock_added_config_entry: ConfigEntry
) -> None:
    """Test load and unload an entry."""

    assert mock_added_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_added_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_added_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_adding_processor_to_options(
    hass: HomeAssistant, mock_added_config_entry: ConfigEntry
) -> None:
    """Test options listener."""
    process_sensor = hass.states.get("binary_sensor.system_monitor_process_systemd")
    assert process_sensor is None

    result = await hass.config_entries.options.async_init(
        mock_added_config_entry.entry_id
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROCESS: ["python3", "pip", "systemd"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "binary_sensor": {
            CONF_PROCESS: ["python3", "pip", "systemd"],
        },
        "resources": [
            "disk_use_percent_/",
            "disk_use_percent_/home/notexist/",
            "memory_free_",
            "network_out_eth0",
            "process_python3",
        ],
    }

    process_sensor = hass.states.get("binary_sensor.system_monitor_process_systemd")
    assert process_sensor is not None
    assert process_sensor.state == STATE_OFF


async def test_migrate_process_sensor_to_binary_sensors(
    hass: HomeAssistant,
    mock_psutil: Mock,
    mock_os: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test process not exist failure."""
    mock_config_entry = MockConfigEntry(
        title="System Monitor",
        domain=DOMAIN,
        data={},
        options={
            "sensor": {"process": ["python3", "pip"]},
            "resources": [
                "disk_use_percent_/",
                "disk_use_percent_/home/notexist/",
                "memory_free_",
                "network_out_eth0",
                "process_python3",
            ],
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    process_sensor = hass.states.get("sensor.system_monitor_process_python3")
    assert process_sensor is not None
    assert process_sensor.state == STATE_ON
    process_sensor = hass.states.get("binary_sensor.system_monitor_process_python3")
    assert process_sensor is not None
    assert process_sensor.state == STATE_ON
