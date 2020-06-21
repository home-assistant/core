"""The tests for the simulated sensor."""
import unittest

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
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestSimulatedSensor(unittest.TestCase):
    """Test the simulated sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_default_config(self):
        """Test default config."""
        config = {"sensor": {"platform": "simulated"}}
        assert setup_component(self.hass, "sensor", config)
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == 1
        state = self.hass.states.get("sensor.simulated")

        assert state.attributes.get(CONF_FRIENDLY_NAME) == DEFAULT_NAME
        assert state.attributes.get(CONF_AMP) == DEFAULT_AMP
        assert state.attributes.get(CONF_UNIT) is None
        assert state.attributes.get(CONF_MEAN) == DEFAULT_MEAN
        assert state.attributes.get(CONF_PERIOD) == 60.0
        assert state.attributes.get(CONF_PHASE) == DEFAULT_PHASE
        assert state.attributes.get(CONF_FWHM) == DEFAULT_FWHM
        assert state.attributes.get(CONF_SEED) == DEFAULT_SEED
        assert state.attributes.get(CONF_RELATIVE_TO_EPOCH) == DEFAULT_RELATIVE_TO_EPOCH
