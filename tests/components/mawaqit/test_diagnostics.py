"""Test Mawaqit diagnostics."""

from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics_returns_expected_keys(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_mosque_data: dict,
    mock_prayer_data: dict,
    setup_mawaqit_integration,
) -> None:
    """Test that diagnostics output contains the three expected top-level keys."""
    await setup_mawaqit_integration(
        mosque_data=mock_mosque_data, prayer_data=mock_prayer_data
    )

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert "config_entry_data" in result
    config_entry_data = result["config_entry_data"]
    assert config_entry_data[CONF_API_KEY] == "**REDACTED**"
    assert config_entry_data[CONF_LATITUDE] == "**REDACTED**"
    assert config_entry_data[CONF_LONGITUDE] == "**REDACTED**"

    assert "mosque_data" in result
    assert result["mosque_data"] == mock_mosque_data

    assert "prayer_times_data" in result
    assert result["prayer_times_data"] == mock_prayer_data
