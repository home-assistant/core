"""Test APCUPSd diagnostics reporting abilities."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from . import MOCK_STATUS, async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test diagnostics report function."""
    entry = await async_init_integration(hass, status=MOCK_STATUS)

    reported = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert reported == MOCK_STATUS | {"SERIALNO": REDACTED}
