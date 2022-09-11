"""Tests for the Wemo number entity."""

import unittest.mock as mock

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.wemo.number import DimmerBrightness
from homeassistant.const import ATTR_ENTITY_ID


@pytest.fixture
def pywemo_model():
    """Pywemo Dimmer number platform."""
    return "Dimmer"


@pytest.fixture
def wemo_entity_suffix():
    """Select the DimmerBrightness entity."""
    return DimmerBrightness._name_suffix.lower()


async def test_registry_state_callback(
    hass, pywemo_registry, pywemo_device, wemo_entity
):
    """Verify that the number receives state updates from the registry."""
    pywemo_device.get_brightness.return_value = 80
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == "204.0"


async def test_set_brightness(hass, pywemo_device, wemo_entity):
    """Verify setting the number updates the brightness correctly."""
    device_brightness = 0

    def set_brightness(brightness):
        nonlocal device_brightness
        device_brightness = brightness

    pywemo_device.get_brightness.side_effect = lambda: device_brightness
    pywemo_device.basicevent = mock.Mock()
    pywemo_device.basicevent.SetBinaryState.side_effect = set_brightness

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id], ATTR_VALUE: 204},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == "204.0"
    pywemo_device.basicevent.SetBinaryState.assert_called_once_with(brightness=80)
