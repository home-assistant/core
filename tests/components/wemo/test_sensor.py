"""Tests for the Wemo sensor entity."""

import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.wemo import CONF_DISCOVERY, CONF_STATIC
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import entity_test_helpers
from .conftest import MOCK_HOST, MOCK_PORT


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

    @pytest.fixture(name="wemo_entity")
    @classmethod
    async def async_wemo_entity_fixture(cls, hass, pywemo_device):
        """Fixture for a Wemo entity in hass."""
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_DISCOVERY: False,
                    CONF_STATIC: [f"{MOCK_HOST}:{MOCK_PORT}"],
                },
            },
        )
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        correct_entity = None
        to_remove = []
        for entry in entity_registry.entities.values():
            if entry.entity_id.endswith(cls.ENTITY_ID_SUFFIX):
                correct_entity = entry
            else:
                to_remove.append(entry.entity_id)

        for removal in to_remove:
            entity_registry.async_remove(removal)
        assert len(entity_registry.entities) == 1
        return correct_entity

    # Tests that are in common among wemo platforms. These test methods will be run
    # in the scope of this test module. They will run using the pywemo_model from
    # this test module (Insight).
    async def test_async_update_locked_multiple_updates(
        self, hass, pywemo_registry, wemo_entity, pywemo_device
    ):
        """Test that two hass async_update state updates do not proceed at the same time."""
        pywemo_device.subscription_update.return_value = False
        await entity_test_helpers.test_async_update_locked_multiple_updates(
            hass,
            pywemo_registry,
            wemo_entity,
            pywemo_device,
            update_polling_method=pywemo_device.update_insight_params,
        )

    async def test_async_update_locked_multiple_callbacks(
        self, hass, pywemo_registry, wemo_entity, pywemo_device
    ):
        """Test that two device callback state updates do not proceed at the same time."""
        pywemo_device.subscription_update.return_value = False
        await entity_test_helpers.test_async_update_locked_multiple_callbacks(
            hass,
            pywemo_registry,
            wemo_entity,
            pywemo_device,
            update_polling_method=pywemo_device.update_insight_params,
        )

    async def test_async_update_locked_callback_and_update(
        self, hass, pywemo_registry, wemo_entity, pywemo_device
    ):
        """Test that a callback and a state update request can't both happen at the same time."""
        pywemo_device.subscription_update.return_value = False
        await entity_test_helpers.test_async_update_locked_callback_and_update(
            hass,
            pywemo_registry,
            wemo_entity,
            pywemo_device,
            update_polling_method=pywemo_device.update_insight_params,
        )

    async def test_async_locked_update_with_exception(
        self, hass, wemo_entity, pywemo_device
    ):
        """Test that the entity becomes unavailable when communication is lost."""
        await entity_test_helpers.test_async_locked_update_with_exception(
            hass,
            wemo_entity,
            pywemo_device,
            update_polling_method=pywemo_device.update_insight_params,
            expected_state=self.EXPECTED_STATE_VALUE,
        )

    async def test_async_update_with_timeout_and_recovery(
        self, hass, wemo_entity, pywemo_device
    ):
        """Test that the entity becomes unavailable after a timeout, and that it recovers."""
        await entity_test_helpers.test_async_update_with_timeout_and_recovery(
            hass, wemo_entity, pywemo_device, expected_state=self.EXPECTED_STATE_VALUE
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
