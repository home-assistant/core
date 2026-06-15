"""Tests for PowerShades diagnostics."""

from homeassistant.core import HomeAssistant

from .conftest import TEST_IP, TEST_NAME, TEST_SERIAL

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry,
) -> None:
    """Diagnostics redact identifying info and include coordinator state."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    entry_data = result["entry_data"]
    assert entry_data["ip"] == "**REDACTED**"
    assert entry_data["mac"] == "**REDACTED**"
    assert entry_data["serial"] == "**REDACTED**"
    assert entry_data["unique_id"] == "**REDACTED**"
    assert entry_data["name"] == TEST_NAME
    assert entry_data["model"] == 1

    assert result["coordinator_data"]["position"] == 50

    # Sanity check the test fixture didn't change underneath us
    assert config_entry.data["ip"] == TEST_IP
    assert config_entry.unique_id == str(TEST_SERIAL)
