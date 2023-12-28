"""Test the Tessie update platform."""
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_updates(hass: HomeAssistant) -> None:
    """Tests that update entity is correct."""

    assert len(hass.states.async_all("update")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("update")) == 1

    assert hass.states.get("update.test").state == STATE_ON
