"""Test pegel_online component."""

from unittest.mock import patch

from aiohttp.client_exceptions import ClientError

from homeassistant.components.pegel_online.const import (
    CONF_STATION,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import utcnow

from . import PegelOnlineMock
from .const import (
    MOCK_CONFIG_ENTRY_DATA_DRESDEN,
    MOCK_STATION_DETAILS_DRESDEN,
    MOCK_STATION_MEASUREMENT_DRESDEN,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update_error(hass: HomeAssistant) -> None:
    """Tests error during update entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA_DRESDEN,
        unique_id=MOCK_CONFIG_ENTRY_DATA_DRESDEN[CONF_STATION],
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.pegel_online.PegelOnline") as pegelonline:
        pegelonline.return_value = PegelOnlineMock(
            station_details=MOCK_STATION_DETAILS_DRESDEN,
            station_measurements=MOCK_STATION_MEASUREMENT_DRESDEN,
        )
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    state = hass.states.get("sensor.dresden_elbe_water_level")
    assert state

    pegelonline().override_side_effect(ClientError)
    async_fire_time_changed(hass, utcnow() + MIN_TIME_BETWEEN_UPDATES)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.dresden_elbe_water_level")
    assert state.state == STATE_UNAVAILABLE
