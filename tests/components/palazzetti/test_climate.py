"""Tests for the Palazzetti climate platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

CLIMATE_ID = f"{Platform.CLIMATE}.stove"


async def test_climate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_palazzetti: AsyncMock,
) -> None:
    """Test the creation and values of Palazzetti climate device."""
    patch("pypalazzetti.client.PalazzettiClient", mock_palazzetti)

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_is_registered(CLIMATE_ID)

    entity = entity_registry.async_get(CLIMATE_ID)

    assert entity.unique_id == "11:22:33:44:55:66"
