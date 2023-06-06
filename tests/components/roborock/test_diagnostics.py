"""Tests for the diagnostics data provided by the Roborock integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.roborock.mock_data import USER_DATA
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
) -> None:
    """Test diagnostics for config entry."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)

    assert isinstance(result, dict)
    assert result["config_entry"]["data"]["username"] == "**REDACTED**"
    assert result["config_entry"]["data"]["base_url"] == "https://usiot.roborock.com"
    assert result["config_entry"]["data"]["user_data"] == {
        **USER_DATA.as_dict(),
        **{"uid": "**REDACTED**", "token": "**REDACTED**", "rruid": "**REDACTED**"},
    }
