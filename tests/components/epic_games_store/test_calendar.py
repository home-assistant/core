"""Tests for the Epic Games Store calendars."""

import datetime
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import setup_platform


def _local_datetime(year, month, day, hour=0):
    """Build a datetime object for testing in the correct timezone."""
    return dt_util.as_local(datetime.datetime(year, month, day, hour, 0, 0))


async def test_setup_component(hass: HomeAssistant, service_multiple: Mock) -> None:
    """Test setup component with calendars."""
    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_discount_games")
    assert state.name == "Epic Games Store Discount Games"
    state = hass.states.get("calendar.epic_games_store_free_games")
    assert state.name == "Epic Games Store Free Games"


# @patch("homeassistant.util.dt.now", return_value=_local_datetime(2022, 11, 1))
async def test_free_games(
    # mock_now,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_multiple: Mock,
) -> None:
    """Test setup component with calendars."""
    freezer.move_to("2022-11-01T15:00:00.000Z")

    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_free_games")
    # assert state.state == STATE_ON
    cal_attrs = dict(state.attributes)
    cal_games = cal_attrs.pop("games")
    assert cal_attrs == {
        "friendly_name": "Epic Games Store Free Games",
        "message": "Rising Storm 2: Vietnam",
        "all_day": False,
        "start_time": "2022-11-03 08:00:00",
        "end_time": "2022-11-10 08:00:00",
        "location": "",
        "description": "Red Orchestra Series' take on Vietnam: 64-player MP matches; 20+ maps; US Army & Marines, PAVN/NVA, NLF/VC; Australians and ARVN forces; 50+ weapons; 4 flyable helicopters; mines, traps and tunnels; Brutal. Authentic. Gritty. Character customization.\n\nhttps://store.epicgames.com/fr/p/rising-storm-2-vietnam",
    }
    assert len(cal_games) == 4


# @patch(
#     "homeassistant.util.dt.now",
#     return_value=dt_util.as_local(datetime.datetime(2015, 11, 27, 0, 15)),
# )
# async def test_calendars(hass: HomeAssistant, service_multiple: Mock) -> None:
#     """Test raid array degraded binary sensor."""
#     assert await async_setup_component(hass, "calendar", {"calendar": CAL_CONFIG})
#     await hass.async_block_till_done()

#     entry = MockConfigEntry(
#         domain=DOMAIN,
#         data={CONF_LOCALE: MOCK_LOCALE},
#         unique_id=MOCK_LOCALE,
#     )
#     entry.add_to_hass(hass)
#     assert await async_setup_component(hass, DOMAIN, {})
#     await hass.async_block_till_done()

#     assert (
#         hass.states.get("binary_sensor.freebox_server_r2_raid_array_0_degraded").state
#         == "off"
#     )

#     # Now simulate we degraded
#     data_storage_get_raids_degraded = deepcopy(DATA_STORAGE_GET_RAIDS)
#     data_storage_get_raids_degraded[0]["degraded"] = True
#     router().storage.get_raids.return_value = data_storage_get_raids_degraded
#     # Simulate an update
#     async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
#     # To execute the save
#     await hass.async_block_till_done()
#     assert (
#         hass.states.get("binary_sensor.freebox_server_r2_raid_array_0_degraded").state
#         == "on"
#     )
