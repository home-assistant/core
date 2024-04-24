"""Test System Monitor binary sensor."""

from datetime import timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.systemmonitor.binary_sensor import get_cpu_icon
from homeassistant.components.systemmonitor.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockProcess

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_psutil: Mock,
    mock_os: Mock,
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


async def test_binary_sensor_icon(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    mock_psutil: Mock,
    mock_os: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor icon for 32bit/64bit system."""

    get_cpu_icon.cache_clear()
    with patch("sys.maxsize", 2**32):
        assert get_cpu_icon() == "mdi:cpu-32-bit"
    get_cpu_icon.cache_clear()
    with patch("sys.maxsize", 2**64):
        assert get_cpu_icon() == "mdi:cpu-64-bit"


async def test_sensor_process_fails(
    hass: HomeAssistant,
    mock_added_config_entry: ConfigEntry,
    mock_psutil: Mock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test process not exist failure."""
    process_sensor = hass.states.get("binary_sensor.system_monitor_process_python3")
    assert process_sensor is not None
    assert process_sensor.state == STATE_ON

    _process = MockProcess("python3", True)

    mock_psutil.process_iter.return_value = [_process]

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    process_sensor = hass.states.get("binary_sensor.system_monitor_process_python3")
    assert process_sensor is not None
    assert process_sensor.state == STATE_OFF

    assert "Failed to load process with ID: 1, old name: python3" in caplog.text
