"""The tests for the Button component."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN, SERVICE_PRESS, ButtonEntity
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import mock_restore_cache


async def test_button(hass: HomeAssistant) -> None:
    """Test getting data from the mocked button entity."""
    button = ButtonEntity()
    assert button.state is None

    button.hass = hass

    with pytest.raises(NotImplementedError):
        await button.async_press()

    button.press = MagicMock()
    await button.async_press()

    assert button.press.called


async def test_custom_integration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test we integration."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get("button.button_1").state == STATE_UNKNOWN

    now = dt_util.utcnow()
    with patch("homeassistant.core.dt_util.utcnow", return_value=now):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.button_1"},
            blocking=True,
        )

    assert hass.states.get("button.button_1").state == now.isoformat()
    assert "The button has been pressed" in caplog.text


async def test_restore_state(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test we restore state integration."""
    mock_restore_cache(hass, (State("button.button_1", "2021-01-01T23:59:59+00:00"),))

    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get("button.button_1").state == "2021-01-01T23:59:59+00:00"
