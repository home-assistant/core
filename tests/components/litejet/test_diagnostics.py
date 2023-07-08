"""The tests for the litejet component."""
from homeassistant.core import HomeAssistant

from . import async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_litejet
) -> None:
    """Test getting the LiteJet diagnostics."""

    config_entry = await async_init_integration(hass)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag == {
        "loads": [1, 2],
        "button_switches": [1, 2],
        "scenes": [1, 2],
        "connected": True,
    }
