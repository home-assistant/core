"""Tests for Vodafone Station sensor platform."""

from copy import deepcopy
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import (
    DOMAIN,
    LINE_TYPES,
    SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_DATA, SENSOR_DATA_QUERY

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("connection_type", "index"),
    [
        ("dsl_ipaddr", 0),
        ("fiber_ipaddr", 1),
        ("vf_internet_key_ip_addr", 2),
    ],
)
async def test_active_connection_type(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
    connection_type,
    index,
) -> None:
    """Test device connection type."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    active_connection_entity = f"sensor.vodafone_station_{SENSOR_DATA_QUERY['sys_serial_number']}_active_connection"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(active_connection_entity)
    assert state
    assert state.state == "unknown"

    sensor_data = deepcopy(SENSOR_DATA_QUERY)
    sensor_data[connection_type] = "1.1.1.1"
    mock_vodafone_station_router.get_sensor_data.return_value = sensor_data

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(active_connection_entity)
    assert state
    assert state.state == LINE_TYPES[index]


@pytest.mark.freeze_time("2023-12-02T13:00:00+00:00")
async def test_uptime(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
) -> None:
    """Test device uptime shift."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    uptime = "2024-11-19T20:19:00+00:00"
    uptime_entity = (
        f"sensor.vodafone_station_{SENSOR_DATA_QUERY['sys_serial_number']}_uptime"
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(uptime_entity)
    assert state
    assert state.state == uptime

    mock_vodafone_station_router.get_sensor_data.return_value["sys_uptime"] = "12:17:23"

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(uptime_entity)
    assert state
    assert state.state == uptime
