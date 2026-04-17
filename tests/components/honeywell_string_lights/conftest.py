"""Common fixtures for the Honeywell String Lights tests."""

from __future__ import annotations

import pytest

from homeassistant.components.honeywell_string_lights.const import (
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.components.radio_frequency import DATA_COMPONENT, DOMAIN as RF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.radio_frequency.conftest import MockRadioFrequencyEntity


@pytest.fixture
async def mock_transmitter(hass: HomeAssistant) -> MockRadioFrequencyEntity:
    """Set up the radio_frequency component and register a mock transmitter."""
    assert await async_setup_component(hass, RF_DOMAIN, {})
    await hass.async_block_till_done()

    entity = MockRadioFrequencyEntity("test_rf_transmitter")
    component = hass.data[DATA_COMPONENT]
    await component.async_add_entities([entity])
    return entity


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_transmitter: MockRadioFrequencyEntity
) -> MockConfigEntry:
    """Return a mock config entry for Honeywell String Lights."""
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(mock_transmitter.entity_id)
    assert entity_entry is not None
    return MockConfigEntry(
        domain=DOMAIN,
        title="Honeywell String Lights",
        data={CONF_TRANSMITTER: entity_entry.id},
        unique_id=entity_entry.id,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Honeywell String Lights integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
