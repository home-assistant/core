"""Test the IMGW-PIB sensor platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from imgw_pib import ApiError
from syrupy import SnapshotAssertion

from homeassistant.components.imgw_pib.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HYDROLOGICAL_DATA, init_integration

from tests.common import async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.river_name_station_name_water_level"


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.imgw_pib.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_availability(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "526.0"

    with patch(
        "homeassistant.components.imgw_pib.ImgwPib.get_hydrological_data",
        side_effect=ApiError("API Error"),
    ):
        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state
        assert state.state == STATE_UNAVAILABLE

    with (
        patch(
            "homeassistant.components.imgw_pib.ImgwPib.get_hydrological_data",
            return_value=HYDROLOGICAL_DATA,
        ),
    ):
        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "526.0"
