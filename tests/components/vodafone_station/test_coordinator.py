"""Define tests for the Vodafone Station coordinator."""

from datetime import datetime
from unittest.mock import patch

from aiovodafone import CannotAuthenticate
from aiovodafone.exceptions import AlreadyLogged, CannotConnect
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.vodafone_station.coordinator import CONSIDER_HOME_SECONDS
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .const import (
    DEVICE_1,
    DEVICE_1_MAC,
    DEVICE_2,
    DEVICE_DATA_QUERY,
    MOCK_USER_DATA,
    SENSOR_DATA_QUERY,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "side_effect",
    [
        CannotConnect,
        CannotAuthenticate,
        AlreadyLogged,
        ConnectionResetError,
    ],
)
async def test_coordinator_client_connector_error(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, side_effect
) -> None:
    """Test ClientConnectorError on coordinator update."""

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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_login.assert_called_once()
        mock_devices_data.assert_called_once()
        mock_sensor_data.assert_called_once()

        mock_devices_data.reset_mock()
        mock_sensor_data.reset_mock()

        mock_devices_data.side_effect = side_effect
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(
            f"sensor.vodafone_station_{SENSOR_DATA_QUERY['sys_serial_number']}_uptime"
        )
        assert state
        assert state.state == STATE_UNAVAILABLE


async def test_coordinator_uptime_shift(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test Device cleanup on coordinator update."""

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

        mock_sensor_data.reset_mock()

        SENSOR_DATA_QUERY["sys_uptime"] = "12:17:23"
        mock_sensor_data.return_value = SENSOR_DATA_QUERY

        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(uptime_entity)
        assert state
        assert state.state == uptime


async def test_coordinator_device_cleanup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test Device cleanup on coordinator update."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with (
        patch("aiovodafone.api.VodafoneStationSercommApi.login") as mock_login,
        patch(
            "aiovodafone.api.VodafoneStationSercommApi.get_devices_data",
            return_value=DEVICE_DATA_QUERY,
        ) as mock_devices_data,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_login.assert_called_once()
        mock_devices_data.assert_called_once()

        mock_devices_data.reset_mock()
        mock_devices_data.return_value = DEVICE_2

        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(f"device_tracker.vodafone_station_{DEVICE_1_MAC}")
        assert state is None


async def test_coordinator_consider_home(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if device is considered not_home when disconnected."""

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
            "homeassistant.components.vodafone_station.device_tracker.VodafoneStationTracker.entity_registry_enabled_default",
            return_value=True,
        ),
    ):
        device_tracker = (
            f"device_tracker.vodafone_station_{DEVICE_1_MAC.replace(":", "_")}"
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_login.assert_called_once()
        mock_devices_data.assert_called_once()
        mock_sensor_data.assert_called_once()

        state = hass.states.get(device_tracker)
        assert state
        assert state.state == "home"

        mock_devices_data.reset_mock()

        DEVICE_1[DEVICE_1_MAC].connected = False
        DEVICE_DATA_QUERY.update(DEVICE_1)
        mock_devices_data.return_value = DEVICE_DATA_QUERY

        freezer.tick(SCAN_INTERVAL + CONSIDER_HOME_SECONDS)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get(device_tracker)
        assert state
        assert state.state == "not_home"
