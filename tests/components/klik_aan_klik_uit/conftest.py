"""Common fixtures for Kaku RC tests."""

import pytest

from homeassistant.components.klik_aan_klik_uit.const import (
    CONF_CHANNEL,
    CONF_DEVICE_ID,
    CONF_GROUP,
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
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> MockConfigEntry:
    """Return a mock config entry for Kaku RC setup."""
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    assert entity_entry is not None

    return MockConfigEntry(
        domain=DOMAIN,
        title="Kaku ID 123456 CH 1",
        data={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_DEVICE_ID: 123456,
            CONF_CHANNEL: 1,
            CONF_GROUP: False,
        },
        unique_id=f"{entity_entry.id}_123456_1_0",
    )


@pytest.fixture
async def init_klik_aan_klik_uit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up Kaku RC integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
