"""Common tests for the Cielo Home."""

from unittest.mock import MagicMock

from homeassistant.components.cielo_home.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_async_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    entity_reg = er.async_get(hass)
    entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == DOMAIN and e.domain == "climate"
    ]
    assert len(entities) == 1

    # Unload
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
