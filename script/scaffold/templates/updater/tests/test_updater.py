"""Test the NEW_NAME updater platform."""
from homeassistant.components.NEW_DOMAIN.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import get_integration_updates


async def test_pending_updates(hass: HomeAssistant) -> None:
    """Test getting NEW_NAME updates."""
    assert await get_integration_updates(hass, DOMAIN) == []
