"""Test for System Monitor init."""
from __future__ import annotations

from homeassistant.components.systemmonitor.const import CONF_PROCESS
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_load_unload_entry(
    hass: HomeAssistant, mock_added_config_entry: ConfigEntry
) -> None:
    """Test load and unload an entry."""

    assert mock_added_config_entry.state == ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_added_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_added_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_adding_processor_to_options(
    hass: HomeAssistant, mock_added_config_entry: ConfigEntry
) -> None:
    """Test options listener."""
    process_sensor = hass.states.get("sensor.system_monitor_process_systemd")
    assert process_sensor is None

    result = await hass.config_entries.options.async_init(
        mock_added_config_entry.entry_id
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROCESS: ["python3", "pip", "systemd"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "sensor": {
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

    process_sensor = hass.states.get("sensor.system_monitor_process_systemd")
    assert process_sensor is not None
    assert process_sensor.state == STATE_OFF
