"""Common fixtures for the Vacmaster Cardio54 tests."""

import pytest

from homeassistant.components.vacmaster_cardio54.const import (
    CONF_DEVICE_ID,
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

TRANSMITTER_ENTITY_ID = "radio_frequency.test_rf_transmitter"

# Deterministic 20-bit device ID used across the suite.
TEST_DEVICE_ID = 0xABCDE


@pytest.fixture
def mock_config_entry(
    mock_rf_entity: MockRadioFrequencyEntity,
    entity_registry: er.EntityRegistry,
) -> MockConfigEntry:
    """Return a mock config entry for Vacmaster Cardio54."""
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    assert entity_entry is not None
    return MockConfigEntry(
        domain=DOMAIN,
        title="Vacmaster Cardio54",
        data={
            CONF_TRANSMITTER: entity_entry.id,
            CONF_DEVICE_ID: TEST_DEVICE_ID,
        },
        unique_id=f"{entity_entry.id}_{TEST_DEVICE_ID:05X}",
    )


@pytest.fixture
async def init_vacmaster_cardio54(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Vacmaster Cardio54 integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
