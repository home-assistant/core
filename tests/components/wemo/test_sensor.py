"""Tests for the Wemo sensor entity."""

import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component

from . import entity_test_helpers


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


class InsightTestTemplate:
    """Base class for testing WeMo Insight Sensors."""

    ENTITY_ID_SUFFIX: str
    EXPECTED_STATE_VALUE: str
    INSIGHT_PARAM_NAME: str

    @pytest.fixture(name="wemo_entity_suffix")
    @classmethod
    def wemo_entity_suffix_fixture(cls):
        """Select the appropriate entity for the test."""
        return cls.ENTITY_ID_SUFFIX

    # Tests that are in common among wemo platforms. These test methods will be run
    # in the scope of this test module. They will run using the pywemo_model from
    # this test module (Insight).
    async def test_async_update_locked_multiple_updates(
        self, hass, pywemo_device, wemo_entity
    ):
        """Test that two hass async_update state updates do not proceed at the same time."""
        await entity_test_helpers.test_async_update_locked_multiple_updates(
            hass,
            pywemo_device,
            wemo_entity,
        )

    async def test_async_update_locked_multiple_callbacks(
        self, hass, pywemo_device, wemo_entity
    ):
        """Test that two device callback state updates do not proceed at the same time."""
        await entity_test_helpers.test_async_update_locked_multiple_callbacks(
            hass,
            pywemo_device,
            wemo_entity,
        )

    async def test_async_update_locked_callback_and_update(
        self, hass, pywemo_device, wemo_entity
    ):
        """Test that a callback and a state update request can't both happen at the same time."""
        await entity_test_helpers.test_async_update_locked_callback_and_update(
            hass,
            pywemo_device,
            wemo_entity,
        )

    async def test_state_unavailable(self, hass, wemo_entity, pywemo_device):
        """Test that there is no failure if the insight_params is not populated."""
        del pywemo_device.insight_params[self.INSIGHT_PARAM_NAME]
        await async_setup_component(hass, HA_DOMAIN, {})
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
            blocking=True,
        )
        assert hass.states.get(wemo_entity.entity_id).state == STATE_UNAVAILABLE


class TestInsightCurrentPower(InsightTestTemplate):
    """Test the InsightCurrentPower class."""

    ENTITY_ID_SUFFIX = "_current_power"
    EXPECTED_STATE_VALUE = "0.001"
    INSIGHT_PARAM_NAME = "currentpower"


class TestInsightTodayEnergy(InsightTestTemplate):
    """Test the InsightTodayEnergy class."""

    ENTITY_ID_SUFFIX = "_today_energy"
    EXPECTED_STATE_VALUE = "3.33"
    INSIGHT_PARAM_NAME = "todaymw"
