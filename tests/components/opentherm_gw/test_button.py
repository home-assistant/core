"""Test opentherm_gw buttons."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_button_platform_setup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test buttons get added during setup."""
    # We need a fixture for the mock config entry
