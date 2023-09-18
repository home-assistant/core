"""Tests for the Epic Games Store calendars."""


from unittest.mock import Mock

from homeassistant.components.epic_games_store.const import CONF_LOCALE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_LOCALE

from tests.common import MockConfigEntry

CAL_CONFIG = {
    "platform": DOMAIN,
}


async def test_setup_component(hass: HomeAssistant, service_multiple: Mock) -> None:
    """Test setup component with calendars."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_LOCALE: MOCK_LOCALE},
        unique_id=MOCK_LOCALE,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.epic_games_store_discount_games")
    assert state.name == "Epic Games Store Discount Games"
    state = hass.states.get("calendar.epic_games_store_free_games")
    assert state.name == "Epic Games Store Free Games"


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
