"""Define tests for the Vodafone Station coordinator."""

from unittest.mock import AsyncMock

from aiovodafone import VodafoneStationDevice
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import DEVICE_1_MAC, DEVICE_2_MAC

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_device_cleanup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Device cleanup on coordinator update."""

    await setup_integration(hass, mock_config_entry)

    device_tracker = f"device_tracker.vodafone_station_{DEVICE_1_MAC.replace(':', '_')}"

    state = hass.states.get(device_tracker)
    assert state is not None

    mock_vodafone_station_router.get_devices_data.return_value = {
        DEVICE_2_MAC: VodafoneStationDevice(
            connected=True,
            connection_type="lan",
            ip_address="192.168.1.11",
            name="LanDevice1",
            mac=DEVICE_2_MAC,
            type="desktop",
            wifi="",
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(device_tracker)
    assert state is None
