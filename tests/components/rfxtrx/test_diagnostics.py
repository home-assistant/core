"""Tests for the diagnostics data provided by the RFXtrx integration."""

from homeassistant.core import HomeAssistant

from .conftest import setup_rfx_test_cfg

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test diagnostics."""
    mock_entry = await setup_rfx_test_cfg(
        hass, host="1.2.3.4", port=1234, devices={"0b1100cd0213c7f230010f71": {}}
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)

    assert result["entry"]["domain"] == "rfxtrx"
    assert result["entry"]["data"]["host"] == "**REDACTED**"
    assert result["entry"]["data"]["port"] == 1234
    subentry = result["entry"]["subentries"][0]
    assert subentry["subentry_type"] == "device"
    assert subentry["data"]["event_code"] == "0b1100cd0213c7f230010f71"
