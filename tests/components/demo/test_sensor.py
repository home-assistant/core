"""The tests for the demo sensor component."""
from datetime import timedelta

import pytest

from homeassistant import core as ha
from homeassistant.components.demo import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache_with_extra_data


@pytest.mark.parametrize("entity_id, delta", (("sensor.total_energy_kwh", 0.5),))
async def test_energy_sensor(hass: ha.HomeAssistant, entity_id, delta, freezer):
    """Test energy sensors increase periodically."""
    assert await async_setup_component(
        hass, SENSOR_DOMAIN, {SENSOR_DOMAIN: {"platform": DOMAIN}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "0"

    freezer.tick(timedelta(minutes=5, seconds=1))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == str(delta)


@pytest.mark.parametrize("entity_id, delta", (("sensor.total_energy_kwh", 0.5),))
async def test_restore_state(hass: ha.HomeAssistant, entity_id, delta, freezer):
    """Test energy sensors restore state."""
    fake_state = ha.State(
        entity_id,
        "",
    )
    fake_extra_data = {
        "native_value": 2**20,
        "native_unit_of_measurement": None,
    }
    mock_restore_cache_with_extra_data(hass, ((fake_state, fake_extra_data),))

    assert await async_setup_component(
        hass, SENSOR_DOMAIN, {SENSOR_DOMAIN: {"platform": DOMAIN}}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == str(2**20)

    freezer.tick(timedelta(minutes=5, seconds=1))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == str(2**20 + delta)
