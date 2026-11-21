"""Common fixtures for Intertechno TriState tests."""

import pytest

from homeassistant.components.intertechno_tristate.const import (
    CONF_CHANNEL,
    CONF_GROUP,
    CONF_HOUSECODE,
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

TRANSMITTER_ENTITY_ID = "radio_frequency.test_rf_transmitter"


@pytest.fixture
def mock_config_entry(
    mock_rf_entity: MockRadioFrequencyEntity,
) -> MockConfigEntry:
    """Return a mock config entry for Intertechno TriState setup."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Intertechno TriState HC A G 1 CH 1",
        data={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_HOUSECODE: "A",
            CONF_GROUP: 1,
            CONF_CHANNEL: 1,
        },
    )


@pytest.fixture
async def init_intertechno_tristate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up Intertechno TriState integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
