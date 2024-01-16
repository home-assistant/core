"""Test the Teslemetry sensor platform."""
from datetime import timedelta

from aiohttp import ClientConnectionError
from tesla_fleet_api.exceptions import NotAcceptable, VehicleOffline

from homeassistant.components.teslemetry.coordinator import SYNC_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .const import WAKE_ASLEEP, WAKE_AWAKE

from tests.common import async_fire_time_changed

WAIT = timedelta(seconds=SYNC_INTERVAL)


async def test_coordinator_online(
    hass: HomeAssistant, config_entry_mock, teslemetry_vehicle_specific_mock
) -> None:
    """Tests that the coordinator handles online vehicles."""

    config_entry_mock.add_to_hass(hass)

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    teslemetry_vehicle_specific_mock.assert_called_once()


async def test_coordinator_asleep(
    hass: HomeAssistant, config_entry_mock, teslemetry_vehicle_specific_mock
) -> None:
    """Tests that the coordinator handles asleep vehicles."""

    teslemetry_vehicle_specific_mock.return_value.wake_up = WAKE_ASLEEP
    config_entry_mock.add_to_hass(hass)

    teslemetry_vehicle_specific_mock.return_value.wake_up = WAKE_AWAKE
    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
    teslemetry_vehicle_specific_mock.assert_called_once()


async def test_coordinator_error(
    hass: HomeAssistant, config_entry_mock, teslemetry_vehicle_specific_mock
) -> None:
    """Tests that the coordinator handles client errors."""

    config_entry_mock.add_to_hass(hass)

    teslemetry_vehicle_specific_mock.side_effect = NotAcceptable

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()


async def test_coordinator_offline(
    hass: HomeAssistant, config_entry_mock, teslemetry_vehicle_specific_mock
) -> None:
    """Tests that the coordinator handles timeout errors."""

    config_entry_mock.add_to_hass(hass)

    teslemetry_vehicle_specific_mock.side_effect = VehicleOffline

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()


async def test_coordinator_connection(
    hass: HomeAssistant, config_entry_mock, teslemetry_vehicle_specific_mock
) -> None:
    """Tests that the coordinator handles connection errors."""

    config_entry_mock.add_to_hass(hass)

    teslemetry_vehicle_specific_mock.side_effect = ClientConnectionError

    async_fire_time_changed(hass, utcnow() + WAIT)
    await hass.async_block_till_done()
