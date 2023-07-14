"""Test evil genius labs diagnostics."""
import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("platforms", [[]])
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_evil_genius_labs,
    config_entry,
    all_fixture,
    info_fixture,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "info": {
            **info_fixture,
            "wiFiSsidDefault": REDACTED,
            "wiFiSSID": REDACTED,
        },
        "all": all_fixture,
    }
