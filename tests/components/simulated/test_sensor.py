"""The tests for the simulated sensor."""

from homeassistant.components.simulated.sensor import (
    CONF_AMP,
    CONF_FWHM,
    CONF_MEAN,
    CONF_PERIOD,
    CONF_PHASE,
    CONF_RELATIVE_TO_EPOCH,
    CONF_SEED,
    CONF_UNIT,
    DEFAULT_AMP,
    DEFAULT_FWHM,
    DEFAULT_MEAN,
    DEFAULT_NAME,
    DEFAULT_PHASE,
    DEFAULT_RELATIVE_TO_EPOCH,
    DEFAULT_SEED,
)
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_simulated_sensor_default_config(hass: HomeAssistant) -> None:
    """Test default config."""
    config = {"sensor": {"platform": "simulated"}}
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1
    state = hass.states.get("sensor.simulated")

    assert state.attributes.get(CONF_FRIENDLY_NAME) == DEFAULT_NAME
    assert state.attributes.get(CONF_AMP) == DEFAULT_AMP
    assert state.attributes.get(CONF_UNIT) is None
    assert state.attributes.get(CONF_MEAN) == DEFAULT_MEAN
    assert state.attributes.get(CONF_PERIOD) == 60.0
    assert state.attributes.get(CONF_PHASE) == DEFAULT_PHASE
    assert state.attributes.get(CONF_FWHM) == DEFAULT_FWHM
    assert state.attributes.get(CONF_SEED) == DEFAULT_SEED
    assert state.attributes.get(CONF_RELATIVE_TO_EPOCH) == DEFAULT_RELATIVE_TO_EPOCH
