"""Tests for the diagnostics data provided by the KNX integration."""
import json

from homeassistant.components.youtube.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: ComponentSetup,
) -> None:
    """Test diagnostics."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    from tests.common import load_fixture

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, entry
    ) == json.loads(load_fixture("youtube/diagnostics.json"))
