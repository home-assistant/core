"""Common fixtures for the Novy Hood tests."""

from __future__ import annotations

import pytest

from homeassistant.components.novy_hood.const import CONF_TRANSMITTER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.radio_frequency.conftest import (
    MockRadioFrequencyEntity,
    init_integration,  # noqa: F401
    mock_rf_entity,  # noqa: F401
)

TRANSMITTER_ENTITY_ID = "radio_frequency.test_rf_transmitter"


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,  # noqa: F811
) -> MockConfigEntry:
    """Return a mock config entry for Novy Hood."""
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    assert entity_entry is not None
    return MockConfigEntry(
        domain=DOMAIN,
        title="Novy Hood",
        data={CONF_TRANSMITTER: entity_entry.id},
        unique_id=entity_entry.id,
    )


@pytest.fixture
async def init_novy_hood(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Novy Hood integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
