"""Tests for the Nobø Ecohub diagnostics."""

from unittest.mock import MagicMock

from pynobo import nobo as pynobo_nobo
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result == snapshot


async def test_entry_diagnostics_redacts_unknown_model_name(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_nobo_hub: MagicMock,
) -> None:
    """An unknown model's name embeds the serial, so it is dropped; model_id is kept."""
    mock_nobo_hub.components = {
        "999000012345": {
            "serial": "999000012345",
            "name": "Mystery device",
            "zone_id": "1",
            "model": pynobo_nobo.Model(
                model_id="999",
                type=pynobo_nobo.Model.UNKNOWN,
                name="Unknown (serial number: 999 000 012 345)",
            ),
        },
    }

    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    component = result["components"][0]
    assert component["serial"] == REDACTED
    assert component["model"]["model_id"] == "999"
    assert component["model"]["name"] == REDACTED
