"""Common fixtures for the Novy Cooker Hood tests."""

import pytest

from homeassistant.components.novy_cooker_hood.const import CONF_TRANSMITTER, DOMAIN
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

TRANSMITTER_ENTITY_ID = "radio_frequency.test_rf_transmitter"


@pytest.fixture
def mock_config_entry(
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> MockConfigEntry:
    """Return a mock config entry for Novy Cooker Hood."""
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    assert entity_entry is not None
    return MockConfigEntry(
        domain=DOMAIN,
        title="Novy Cooker Hood",
        data={CONF_TRANSMITTER: entity_entry.id, CONF_CODE: 1},
        unique_id=f"{entity_entry.id}_1",
    )


@pytest.fixture
async def init_novy_cooker_hood(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Novy Cooker Hood integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
