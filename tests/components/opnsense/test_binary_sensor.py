"""Tests for the OPNsense binary sensor platform."""

import pytest

from homeassistant.components import binary_sensor
from homeassistant.components.opnsense.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    OPNsenseBinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor platform setup."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    binary_sensor_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    binary_sensor_entities = [
        entity
        for entity in binary_sensor_entities
        if entity.domain == binary_sensor.DOMAIN
    ]

    assert len(binary_sensor_entities) == 2

    entity_unique_ids = {entity.unique_id for entity in binary_sensor_entities}
    assert "ff:ff:ff:ff:ff:ff_expired" in entity_unique_ids
    assert "ff:ff:ff:ff:ff:fe_expired" in entity_unique_ids

    for entity in binary_sensor_entities:
        assert entity.disabled_by is RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_binary_sensor_state_when_enabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test OPNsense binary sensor state."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    binary_sensor_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    expired_entity = next(
        entity
        for entity in binary_sensor_entities
        if entity.unique_id == "ff:ff:ff:ff:ff:ff_expired"
    )

    entity_registry.async_update_entity(expired_entity.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(expired_entity.entity_id)
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_is_on_is_false_when_binary_sensor_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test is_on is False when the tracked device is unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    description = BINARY_SENSOR_DESCRIPTIONS[0]
    coordinator = mock_config_entry.runtime_data.coordinator
    entity = OPNsenseBinarySensorEntity(coordinator, "00:00:00:00:00:00", description)

    assert entity.available is False
    assert entity.is_on is False
