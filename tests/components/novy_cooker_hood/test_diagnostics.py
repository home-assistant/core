"""Tests for the diagnostics provided by the Novy Cooker Hood integration."""

from homeassistant.core import HomeAssistant

from .conftest import TRANSMITTER_ENTITY_ID

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """Test diagnostics returns the entry, entities and transmitter state."""
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, init_novy_cooker_hood
    )

    assert result["config_entry"]["domain"] == "novy_cooker_hood"
    assert result["config_entry"]["data"]["code"] == 1

    entity_ids = {entity["entity_id"] for entity in result["entities"]}
    assert entity_ids == {"light.novy_cooker_hood_light", "fan.novy_cooker_hood"}

    assert result["transmitter"]["entity_id"] == TRANSMITTER_ENTITY_ID
    assert result["transmitter"]["state"] is not None
