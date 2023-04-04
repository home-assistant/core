"""Tests for AVM Fritz!Box templates."""
from unittest.mock import Mock

from homeassistant.components.button import DOMAIN, SERVICE_PRESS
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_DEVICES,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from . import FritzEntityBaseMock, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

ENTITY_ID = f"{DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(hass: HomeAssistant, fritz: Mock) -> None:
    """Test if is initialized correctly."""
    template = FritzEntityBaseMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], fritz=fritz, template=template
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_FRIENDLY_NAME] == CONF_FAKE_NAME
    assert state.state == STATE_UNKNOWN


async def test_apply_template(hass: HomeAssistant, fritz: Mock) -> None:
    """Test if applies works."""
    template = FritzEntityBaseMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], fritz=fritz, template=template
    )

    assert await hass.services.async_call(
        DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert fritz().apply_template.call_count == 1
