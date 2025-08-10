"""Test the OMIE - Spain and Portugal electricity prices integration."""

from homeassistant.components.omie.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


async def test_empty_config(hass: HomeAssistant) -> None:
    """Test setup with empty configuration."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {},
    )
    assert_setup_component(0, DOMAIN)
