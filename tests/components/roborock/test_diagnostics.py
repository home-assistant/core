"""Tests for the diagnostics data provided by the Roborock integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.roborock.const import CONF_CACHED_INFORMATION
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, setup_entry)
    # Since supported entities gets added to asyncly, the list can have different orders.
    for cached_information in result["config_entry"][CONF_CACHED_INFORMATION].values():
        cached_information["supported_entities"] = sorted(
            cached_information["supported_entities"]
        )
    assert isinstance(result, dict)
    assert result == snapshot
