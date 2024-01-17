"""The serive tests for the tado platform."""
from homeassistant.components.tado.const import DOMAIN, SERVICE_ADD_METER_READING
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_has_services(
    hass: HomeAssistant,
) -> None:
    """Test the existence of the Tado Service."""

    await async_init_integration(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_ADD_METER_READING)
