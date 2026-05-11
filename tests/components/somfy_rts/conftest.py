"""Common fixtures for the Somfy RTS tests."""

import pytest

from homeassistant.components.somfy_rts.const import CONF_ADDRESS, CONF_TRANSMITTER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

ADDRESS = 0x1A2B3C
ADDRESS_HEX = "1A2B3C"
TRANSMITTER_ENTITY_ID = "radio_frequency.test_rf_transmitter"
COVER_ENTITY_ID = "cover.somfy_rts_1a2b3c"


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> MockConfigEntry:
    """Return a mock config entry for Somfy RTS."""
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Somfy RTS {ADDRESS_HEX}",
        data={CONF_ADDRESS: ADDRESS, CONF_TRANSMITTER: entity_entry.id},
        unique_id=ADDRESS_HEX,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Somfy RTS integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
