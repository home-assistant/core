"""Test the Fressnapf Tracker diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.fressnapf_tracker.const import (
    CONF_PHONE_NUMBER,
    CONF_USER_ID,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("init_integration")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the diagnostics redact sensitive data and keep the rest."""
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry_data"][CONF_ACCESS_TOKEN] == REDACTED
    assert result["entry_data"][CONF_USER_ID] == REDACTED
    assert result["entry_data"][CONF_PHONE_NUMBER] == REDACTED

    assert len(result["trackers"]) == 1
    tracker = result["trackers"][0]
    assert tracker["device"] == {"serialnumber": REDACTED, "token": REDACTED}
    assert tracker["data"]["name"] == REDACTED
    assert tracker["data"]["icon"] == REDACTED
    assert tracker["data"]["position"]["lat"] == REDACTED
    assert tracker["data"]["position"]["lng"] == REDACTED
    # Non sensitive data is kept to help with debugging
    assert tracker["data"]["battery"] == 85
    assert tracker["data"]["position"]["accuracy"] == 10
