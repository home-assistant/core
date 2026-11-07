"""Test the Fressnapf Tracker diagnostics."""

from http import HTTPStatus
from unittest.mock import MagicMock

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
from homeassistant.setup import async_setup_component

from .conftest import MOCK_ACCESS_TOKEN, MOCK_PHONE_NUMBER, MOCK_SERIAL_NUMBER


@pytest.mark.usefixtures("init_integration")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
) -> None:
    """Test that the diagnostics redact sensitive data and keep the rest."""
    mock_api_client_init.get_tracker.return_value.inside_geofence = True
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
    assert tracker["data"]["inside_geofence"] == REDACTED
    # Non sensitive data is kept to help with debugging
    assert tracker["data"]["battery"] == 85
    assert tracker["data"]["position"]["accuracy"] == 10


@pytest.mark.usefixtures("init_integration")
async def test_download_contains_no_sensitive_values(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the complete download, including what the framework appends."""
    assert await async_setup_component(hass, "diagnostics", {})
    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{mock_config_entry.entry_id}"
    )
    assert response.status == HTTPStatus.OK
    text = await response.text()

    assert MOCK_ACCESS_TOKEN not in text
    assert MOCK_PHONE_NUMBER not in text
    assert MOCK_SERIAL_NUMBER not in text
    assert "Fluffy" not in text
