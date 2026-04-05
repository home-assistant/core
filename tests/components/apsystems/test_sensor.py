"""Test the APSystem sensor module."""

import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SCAN_INTERVAL = datetime.timedelta(seconds=12)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.apsystems.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_sensor_offline_connection_error(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors report correct values when inverter goes offline.

    Power sensors should report 0, energy sensors should retain last known values,
    and no sensor should become unavailable.
    """
    await setup_integration(hass, mock_config_entry)

    # Simulate inverter going offline
    mock_apsystems.get_output_data.side_effect = ConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Power sensors should report 0
    total_power = hass.states.get("sensor.mock_title_total_power")
    assert total_power is not None
    assert total_power.state not in ("unavailable", "unknown")
    assert total_power.state == "0"

    power_p1 = hass.states.get("sensor.mock_title_power_of_p1")
    assert power_p1 is not None
    assert power_p1.state not in ("unavailable", "unknown")
    assert power_p1.state == "0"

    power_p2 = hass.states.get("sensor.mock_title_power_of_p2")
    assert power_p2 is not None
    assert power_p2.state not in ("unavailable", "unknown")
    assert power_p2.state == "0"

    # Energy sensors should retain last known values (from conftest fixture)
    today_prod = hass.states.get("sensor.mock_title_production_of_today")
    assert today_prod is not None
    assert today_prod.state not in ("unavailable", "unknown")
    assert today_prod.state == "9.0"  # e1(3.0) + e2(6.0)

    today_p1 = hass.states.get("sensor.mock_title_production_of_today_from_p1")
    assert today_p1 is not None
    assert today_p1.state not in ("unavailable", "unknown")
    assert today_p1.state == "3.0"  # e1

    today_p2 = hass.states.get("sensor.mock_title_production_of_today_from_p2")
    assert today_p2 is not None
    assert today_p2.state not in ("unavailable", "unknown")
    assert today_p2.state == "6.0"  # e2

    lifetime = hass.states.get("sensor.mock_title_total_lifetime_production")
    assert lifetime is not None
    assert lifetime.state not in ("unavailable", "unknown")
    assert lifetime.state == "11.0"  # te1(4.0) + te2(7.0)

    lifetime_p1 = hass.states.get("sensor.mock_title_lifetime_production_of_p1")
    assert lifetime_p1 is not None
    assert lifetime_p1.state not in ("unavailable", "unknown")
    assert lifetime_p1.state == "4.0"  # te1

    lifetime_p2 = hass.states.get("sensor.mock_title_lifetime_production_of_p2")
    assert lifetime_p2 is not None
    assert lifetime_p2.state not in ("unavailable", "unknown")
    assert lifetime_p2.state == "7.0"  # te2


async def test_sensor_offline_timeout_error(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors report correct values when inverter times out."""
    await setup_integration(hass, mock_config_entry)

    # Simulate inverter timeout
    mock_apsystems.get_output_data.side_effect = TimeoutError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Power sensors should report 0
    assert hass.states.get("sensor.mock_title_total_power").state == "0"
    assert hass.states.get("sensor.mock_title_power_of_p1").state == "0"
    assert hass.states.get("sensor.mock_title_power_of_p2").state == "0"

    # Energy sensors should retain last known values
    assert hass.states.get("sensor.mock_title_production_of_today").state == "9.0"
    assert (
        hass.states.get("sensor.mock_title_total_lifetime_production").state == "11.0"
    )


async def test_sensor_cold_start_offline(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors when inverter is offline from the very first refresh.

    When HA starts and the inverter has never been reachable (no prior data),
    power sensors should report 0 and energy sensors should be unknown.
    """
    mock_apsystems.get_device_info.side_effect = TimeoutError
    mock_apsystems.get_output_data.side_effect = TimeoutError
    mock_apsystems.get_alarm_info.side_effect = TimeoutError

    with patch(
        "homeassistant.components.apsystems.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    # Power sensors should report 0
    assert hass.states.get("sensor.mock_title_total_power").state == "0"
    assert hass.states.get("sensor.mock_title_power_of_p1").state == "0"
    assert hass.states.get("sensor.mock_title_power_of_p2").state == "0"

    # Energy sensors should be unknown (no prior data)
    assert hass.states.get("sensor.mock_title_production_of_today").state == "unknown"
    assert (
        hass.states.get("sensor.mock_title_production_of_today_from_p1").state
        == "unknown"
    )
    assert (
        hass.states.get("sensor.mock_title_production_of_today_from_p2").state
        == "unknown"
    )
    assert (
        hass.states.get("sensor.mock_title_total_lifetime_production").state
        == "unknown"
    )
    assert (
        hass.states.get("sensor.mock_title_lifetime_production_of_p1").state
        == "unknown"
    )
    assert (
        hass.states.get("sensor.mock_title_lifetime_production_of_p2").state
        == "unknown"
    )


async def test_sensor_offline_recovery(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors recover live values after inverter comes back online."""
    await setup_integration(hass, mock_config_entry)

    # Go offline
    mock_apsystems.get_output_data.side_effect = ConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Come back online
    mock_apsystems.get_output_data.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # All sensors should report live values again (from conftest fixture)
    assert hass.states.get("sensor.mock_title_total_power").state == "7.0"
    assert hass.states.get("sensor.mock_title_power_of_p1").state == "2.0"
    assert hass.states.get("sensor.mock_title_power_of_p2").state == "5.0"
    assert hass.states.get("sensor.mock_title_production_of_today").state == "9.0"
    assert (
        hass.states.get("sensor.mock_title_production_of_today_from_p1").state == "3.0"
    )
    assert (
        hass.states.get("sensor.mock_title_production_of_today_from_p2").state == "6.0"
    )
    assert (
        hass.states.get("sensor.mock_title_total_lifetime_production").state == "11.0"
    )
    assert hass.states.get("sensor.mock_title_lifetime_production_of_p1").state == "4.0"
    assert hass.states.get("sensor.mock_title_lifetime_production_of_p2").state == "7.0"
