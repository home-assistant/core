"""Test the laundrify coordinator."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DEFAULT_POLL_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed

# The energy sensor entity_id based on the device name "Demo Waschmaschine"
# from fixtures/machines.json. It gets "_2" suffix as it's registered after
# the power sensor which takes the base name.
ENERGY_SENSOR_ENTITY_ID = "sensor.demo_waschmaschine_2"


async def test_coordinator_update_success(
    hass: HomeAssistant,
    laundrify_config_entry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update is performed successfully."""
    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_coordinator_update_unauthorized(
    hass: HomeAssistant,
    laundrify_config_entry,
    laundrify_api_mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update fails if an UnauthorizedException is thrown."""
    laundrify_api_mock.get_machines.side_effect = exceptions.UnauthorizedException

    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_coordinator_update_connection_failed(
    hass: HomeAssistant,
    laundrify_config_entry,
    laundrify_api_mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update fails if an ApiConnectionException is thrown."""
    laundrify_api_mock.get_machines.side_effect = exceptions.ApiConnectionException

    freezer.tick(timedelta(seconds=DEFAULT_POLL_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
