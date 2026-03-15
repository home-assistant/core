"""Common tests for the Cielo Home."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.components.cielo_home.const import DOMAIN
from tests.common import MockConfigEntry


async def test_async_setup_and_unload_entry(
    hass: HomeAssistant, mock_cielo_client: MagicMock
) -> None:
    """Test setting up and unloading the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "ABC1234567890XZY", CONF_TOKEN: "valid-test-token"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None

    entity_reg = er.async_get(hass)
    entities = [
        e
        for e in entity_reg.entities.values()
        if e.platform == DOMAIN and e.domain == "climate"
    ]
    assert len(entities) == 1

    # Unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
