"""Tests for the Tank Utility diagnostics platform."""

import pytest

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .conftest import MOCK_DEVICE_ID

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_get_data")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics redaction and structure."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert "entry" in diagnostics
    assert "data" in diagnostics

    # Verify sensitive data redaction in entry
    assert diagnostics["entry"]["title"] == "**REDACTED**"
    assert diagnostics["entry"]["unique_id"] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_EMAIL] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"

    # Verify sensitive data redaction in device data
    assert diagnostics["data"][MOCK_DEVICE_ID]["address"] == "**REDACTED**"
    assert diagnostics["data"][MOCK_DEVICE_ID]["tank"] == 78.43
    assert diagnostics["data"][MOCK_DEVICE_ID]["capacity"] == 500
