"""Define tests for the Vodafone Station coordinator."""

from unittest.mock import AsyncMock

from aiovodafone import CannotAuthenticate
from aiovodafone.exceptions import AlreadyLogged, CannotConnect
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .const import DEVICE_1_MAC, DEVICE_2, MOCK_USER_DATA, SENSOR_DATA_QUERY

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
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
    side_effect,
) -> None:
    """Test ClientConnectorError on coordinator update."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_vodafone_station_router.get_devices_data.side_effect = side_effect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(
        f"sensor.vodafone_station_{SENSOR_DATA_QUERY['sys_serial_number']}_uptime"
    )
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_coordinator_device_cleanup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
) -> None:
    """Test Device cleanup on coordinator update."""

    device_tracker = f"device_tracker.vodafone_station_{DEVICE_1_MAC}"
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(device_tracker)
    assert state is None

    mock_vodafone_station_router.get_devices_data = DEVICE_2

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(device_tracker)
    assert state is None
