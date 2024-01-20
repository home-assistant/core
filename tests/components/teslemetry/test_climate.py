"""Test the Teslemetry climate platform."""


from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform


async def test_climate(hass: HomeAssistant) -> None:
    """Tests that the climate entity is correct."""

    await setup_platform(hass, [Platform.CLIMATE])

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 1
