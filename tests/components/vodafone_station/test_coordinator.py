"""Define tests for the Vodafone Station coordinator."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import DOMAIN, SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .const import DEVICE_1_MAC, DEVICE_2, MOCK_USER_DATA

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_device_cleanup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
) -> None:
    """Test Device cleanup on coordinator update."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    device_tracker = f"device_tracker.vodafone_station_{DEVICE_1_MAC.replace(":", "_")}"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(device_tracker)
    assert state is not None

    mock_vodafone_station_router.get_devices_data.return_value = DEVICE_2

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(device_tracker)
    assert state is None
