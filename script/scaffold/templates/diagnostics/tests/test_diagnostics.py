"""Test the NEW_NAME diagnostics platform."""
from homeassistant.components.NEW_DOMAIN.const import DOMAIN
from homeassistant.components.NEW_DOMAIN.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics(hass: HomeAssistant) -> None:
    """Test NEW_NAME diagnostics."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    assert async_get_config_entry_diagnostics(hass, config_entry) == {}
