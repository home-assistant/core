"""Tests for the Wemo sensor entity."""

import pytest

from .conftest import MOCK_INSIGHT_CURRENT_WATTS, MOCK_INSIGHT_TODAY_KWH
from .entity_test_helpers import EntityTestHelpers


@pytest.fixture
def pywemo_model():
    """Pywemo LightSwitch models use the switch platform."""
    return "Insight"


@pytest.fixture(name="pywemo_device")
def pywemo_device_fixture(pywemo_device):
    """Fixture for WeMoDevice instances."""
    pywemo_device.insight_params = {
        "currentpower": 1.0,
        "todaymw": 200000000.0,
        "state": 0,
        "onfor": 0,
        "ontoday": 0,
        "ontotal": 0,
        "powerthreshold": 0,
    }
    yield pywemo_device


class InsightTestTemplate(EntityTestHelpers):
    """Base class for testing WeMo Insight Sensors."""

    ENTITY_ID_SUFFIX: str
    EXPECTED_STATE_VALUE: str

    @pytest.fixture(name="wemo_entity_suffix")
    @classmethod
    def wemo_entity_suffix_fixture(cls):
        """Select the appropriate entity for the test."""
        return cls.ENTITY_ID_SUFFIX

    def test_state(self, hass, wemo_entity):
        """Test the sensor state."""
        assert hass.states.get(wemo_entity.entity_id).state == self.EXPECTED_STATE_VALUE


class TestInsightCurrentPower(InsightTestTemplate):
    """Test the InsightCurrentPower class."""

    ENTITY_ID_SUFFIX = "_current_power"
    EXPECTED_STATE_VALUE = str(MOCK_INSIGHT_CURRENT_WATTS)


class TestInsightTodayEnergy(InsightTestTemplate):
    """Test the InsightTodayEnergy class."""

    ENTITY_ID_SUFFIX = "_today_energy"
    EXPECTED_STATE_VALUE = str(MOCK_INSIGHT_TODAY_KWH)
