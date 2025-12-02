"""Test the everHome sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors with snapshot."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_everhome_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test power sensor."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    assert (
        hass.states.get("sensor.everhome_abcdef123456_energy_in").state
        == "77498562.3864"
    )
    assert (
        hass.states.get("sensor.everhome_abcdef123456_energy_in_t1").state == "unknown"
    )
    assert (
        hass.states.get("sensor.everhome_abcdef123456_energy_in_t2").state == "unknown"
    )
    assert hass.states.get("sensor.everhome_abcdef123456_energy_out").state == "unknown"
    assert hass.states.get("sensor.everhome_abcdef123456_power").state == "594.54"
    assert hass.states.get("sensor.everhome_abcdef123456_power_average").state == "606"
    assert (
        hass.states.get("sensor.everhome_abcdef123456_power_phase_1").state == "360.57"
    )
    assert (
        hass.states.get("sensor.everhome_abcdef123456_power_phase_2").state == "101.54"
    )
    assert (
        hass.states.get("sensor.everhome_abcdef123456_power_phase_3").state == "132.42"
    )
    assert hass.states.get("sensor.everhome_abcdef123456_wifi_rssi").state == "-71"

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_everhome_client.get_data.return_value.energy_counter_in = 30000
    mock_everhome_client.get_data.return_value.energy_counter_in_t1 = 4000
    mock_everhome_client.get_data.return_value.energy_counter_in_t2 = 5000
    mock_everhome_client.get_data.return_value.energy_counter_out = 6000
    mock_everhome_client.get_data.return_value.power = 120.4
    mock_everhome_client.get_data.return_value.power_avg = 112
    mock_everhome_client.get_data.return_value.power_phase1 = 40.4
    mock_everhome_client.get_data.return_value.power_phase2 = 40
    mock_everhome_client.get_data.return_value.power_phase3 = 40
    mock_everhome_client.get_data.return_value.rssi = -22

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.everhome_abcdef123456_energy_in").state == "30000"
    assert hass.states.get("sensor.everhome_abcdef123456_energy_in_t1").state == "4000"
    assert hass.states.get("sensor.everhome_abcdef123456_energy_in_t2").state == "5000"
    assert hass.states.get("sensor.everhome_abcdef123456_energy_out").state == "6000"
    assert hass.states.get("sensor.everhome_abcdef123456_power").state == "120.4"
    assert hass.states.get("sensor.everhome_abcdef123456_power_average").state == "112"
    assert hass.states.get("sensor.everhome_abcdef123456_power_phase_1").state == "40.4"
    assert hass.states.get("sensor.everhome_abcdef123456_power_phase_2").state == "40"
    assert hass.states.get("sensor.everhome_abcdef123456_power_phase_3").state == "40"
    assert hass.states.get("sensor.everhome_abcdef123456_wifi_rssi").state == "-22"
