"""Test System Monitor binary sensor."""
from unittest.mock import Mock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.systemmonitor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_util: Mock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the binary sensor."""
    mock_config_entry = MockConfigEntry(
        title="System Monitor",
        domain=DOMAIN,
        data={},
        options={
            "binary_sensor": {"process": ["python3", "pip"]},
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

    process_binary_sensor = hass.states.get(
        "binary_sensor.system_monitor_process_python3"
    )
    assert process_binary_sensor is not None

    for entity in er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ):
        if entity.domain == BINARY_SENSOR_DOMAIN:
            state = hass.states.get(entity.entity_id)
            assert state.state == snapshot(name=f"{state.name} - state")
            assert state.attributes == snapshot(name=f"{state.name} - attributes")
