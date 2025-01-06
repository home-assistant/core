"""Define tests for the Vodafone Station device tracker."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.vodafone_station.coordinator import CONSIDER_HOME_SECONDS
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant

from .const import DEVICE_1, DEVICE_1_MAC, DEVICE_DATA_QUERY, MOCK_USER_DATA

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_consider_home(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
) -> None:
    """Test if device is considered not_home when disconnected."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    device_tracker = f"device_tracker.vodafone_station_{DEVICE_1_MAC.replace(":", "_")}"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(device_tracker)
    assert state
    assert state.state == STATE_HOME

    DEVICE_1[DEVICE_1_MAC].connected = False
    DEVICE_DATA_QUERY.update(DEVICE_1)
    mock_vodafone_station_router.get_devices_data.return_value = DEVICE_DATA_QUERY

    freezer.tick(SCAN_INTERVAL + CONSIDER_HOME_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(device_tracker)
    assert state
    assert state.state == STATE_NOT_HOME
