"""Tests for the Wemo binary_sensor entity."""

import pytest
import pywemo
from pywemo import StandbyState

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.wemo.binary_sensor import (
    InsightBinarySensor,
    MakerBinarySensor,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .entity_test_helpers import EntityTestHelpers


class TestMotion(EntityTestHelpers):
    """Test for the pyWeMo Motion device."""

    @pytest.fixture
    def pywemo_model(self):
        """Pywemo Motion models use the binary_sensor platform."""
        return "Motion"

    async def test_binary_sensor_registry_state_callback(
        self,
        hass: HomeAssistant,
        pywemo_registry: pywemo.SubscriptionRegistry,
        pywemo_device: pywemo.WeMoDevice,
        wemo_entity: er.RegistryEntry,
    ) -> None:
        """Verify that the binary_sensor receives state updates from the registry."""
        # On state.
        pywemo_device.get_state.return_value = 1
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

        # Off state.
        pywemo_device.get_state.return_value = 0
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF

    async def test_binary_sensor_update_entity(
        self,
        hass: HomeAssistant,
        pywemo_registry: pywemo.SubscriptionRegistry,
        pywemo_device: pywemo.WeMoDevice,
        wemo_entity: er.RegistryEntry,
    ) -> None:
        """Verify that the binary_sensor performs state updates."""
        await async_setup_component(hass, HA_DOMAIN, {})

        # On state.
        pywemo_device.get_state.return_value = 1
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
            blocking=True,
        )
        assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

        # Off state.
        pywemo_device.get_state.return_value = 0
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
            blocking=True,
        )
        assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


class TestMaker(EntityTestHelpers):
    """Test for the pyWeMo Maker device."""

    @pytest.fixture
    def pywemo_model(self):
        """Pywemo Motion models use the binary_sensor platform."""
        return "Maker"

    @pytest.fixture
    def wemo_entity_suffix(self):
        """Select the MakerBinarySensor entity."""
        return MakerBinarySensor._name_suffix.lower()

    async def test_registry_state_callback(
        self,
        hass: HomeAssistant,
        pywemo_registry: pywemo.SubscriptionRegistry,
        pywemo_device: pywemo.WeMoDevice,
        wemo_entity: er.RegistryEntry,
    ) -> None:
        """Verify that the binary_sensor receives state updates from the registry."""
        # On state.
        pywemo_device.sensor_state = 0
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

        # Off state.
        pywemo_device.sensor_state = 1
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


class TestInsight(EntityTestHelpers):
    """Test for the pyWeMo Insight device."""

    @pytest.fixture
    def pywemo_model(self):
        """Pywemo Motion models use the binary_sensor platform."""
        return "Insight"

    @pytest.fixture
    def wemo_entity_suffix(self):
        """Select the InsightBinarySensor entity."""
        return InsightBinarySensor._name_suffix.lower()

    async def test_registry_state_callback(
        self,
        hass: HomeAssistant,
        pywemo_registry: pywemo.SubscriptionRegistry,
        pywemo_device: pywemo.WeMoDevice,
        wemo_entity: er.RegistryEntry,
    ) -> None:
        """Verify that the binary_sensor receives state updates from the registry."""
        # On state.
        pywemo_device.get_state.return_value = 1
        pywemo_device.standby_state = StandbyState.ON
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

        # Standby (Off) state.
        pywemo_device.get_state.return_value = 1
        pywemo_device.standby_state = StandbyState.STANDBY
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF

        # Off state.
        pywemo_device.get_state.return_value = 0
        pywemo_device.standby_state = StandbyState.OFF
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        await hass.async_block_till_done()
        assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF
