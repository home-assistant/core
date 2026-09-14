"""Common fixtures for the Honeywell String Lights tests."""

import pytest

from homeassistant.components.honeywell_string_lights.const import (
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

TRANSMITTER_ENTITY_ID = "radio_frequency.test_rf_transmitter"


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> MockConfigEntry:
    """Return a mock config entry for Honeywell String Lights."""
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    return MockConfigEntry(
        domain=DOMAIN,
        title="Honeywell String Lights",
        data={CONF_TRANSMITTER: entity_entry.id},
        unique_id=entity_entry.id,
    )


@pytest.fixture
async def init_string_lights(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Honeywell String Lights integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
