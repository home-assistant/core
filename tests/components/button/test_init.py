"""The tests for the Button component."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from homeassistant.components.button import DOMAIN, SERVICE_PRESS, ButtonEntity
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


class MockButtonEntity(ButtonEntity):
    """Mock ButtonEntity to use in tests."""

    _attr_last_pressed = datetime(2021, 1, 1, 23, 59, 59, tzinfo=dt_util.UTC)


async def test_button(hass: HomeAssistant) -> None:
    """Test getting data from the mocked button entity."""
    button = MockButtonEntity()
    assert button.state == "2021-01-01T23:59:59+00:00"

    button.hass = hass

    with pytest.raises(NotImplementedError):
        await button.async_press()

    button.press = MagicMock()
    await button.async_press()

    assert button.press.called


async def test_custom_integration(hass, enable_custom_integrations):
    """Test we integration."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get("button.button_1").state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.button_1"},
        blocking=True,
    )

    assert hass.states.get("button.button_1").state == "2021-01-01T23:59:59+00:00"
