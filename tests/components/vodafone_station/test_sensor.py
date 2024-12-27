"""Tests for Vodafone Station sensor platform."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import (
    DOMAIN,
    LINE_TYPES,
    SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant

from .const import DEVICE_DATA_QUERY, MOCK_USER_DATA, SENSOR_DATA_QUERY

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
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, connection_type, index
) -> None:
    """Test device connection type."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch("aiovodafone.api.VodafoneStationSercommApi.login") as mock_login,
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_devices_data",
            return_value=DEVICE_DATA_QUERY,
        ) as mock_devices_data,
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_sensor_data",
            return_value=SENSOR_DATA_QUERY,
        ) as mock_sensor_data,
    ):
        active_connection_entity = f"sensor.vodafone_station_{SENSOR_DATA_QUERY['sys_serial_number']}_active_connection"

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_login.assert_called_once()
        mock_devices_data.assert_called_once()
        mock_sensor_data.assert_called_once()

        state = hass.states.get(active_connection_entity)
        assert state
        assert state.state == "unknown"

        sensor_data = deepcopy(SENSOR_DATA_QUERY)
        sensor_data[connection_type] = "1.1.1.1"
        mock_sensor_data.return_value = sensor_data

        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(active_connection_entity)
        assert state
        assert state.state == LINE_TYPES[index]


async def test_uptime(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test device uptime shift."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch("aiovodafone.api.VodafoneStationSercommApi.login") as mock_login,
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_devices_data",
            return_value=DEVICE_DATA_QUERY,
        ) as mock_devices_data,
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_sensor_data",
            return_value=SENSOR_DATA_QUERY,
        ) as mock_sensor_data,
        patch(
            "datetime.datetime.now",
            return_value=datetime.strptime(
                "2024-12-02T13:00:00+0000", "%Y-%m-%dT%H:%M:%S%z"
            ),
        ),
    ):
        uptime = "2024-11-19T20:19:00+00:00"
        uptime_entity = (
            f"sensor.vodafone_station_{SENSOR_DATA_QUERY['sys_serial_number']}_uptime"
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_login.assert_called_once()
        mock_devices_data.assert_called_once()
        mock_sensor_data.assert_called_once()

        state = hass.states.get(uptime_entity)
        assert state
        assert state.state == uptime

        sensor_data = deepcopy(SENSOR_DATA_QUERY)
        sensor_data["sys_uptime"] = "12:17:23"
        mock_sensor_data.return_value = sensor_data

        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(uptime_entity)
        assert state
        assert state.state == uptime
