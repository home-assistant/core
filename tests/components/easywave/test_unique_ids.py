"""Tests to ensure all Easywave entities have valid unique IDs."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_NEO_SENSOR_SERIAL,
    MOCK_TRANSMITTER_SERIAL,
    _entry_with_subentries,
    _neo_sensor_device_record,
    _transmitter_device_record,
    async_setup_easywave_entry,
)

NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)


async def test_transmitter_entities_have_unique_ids_from_setup(
    hass: HomeAssistant,
) -> None:
    """Transmitter entities registered during setup use device-based unique IDs."""
    entry = _entry_with_subentries(_transmitter_device_record(title="Test Transmitter"))
    await async_setup_easywave_entry(hass, entry)

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    transmitter_entities = [
        entity
        for entity in entities
        if entity.unique_id
        and entity.unique_id.startswith(f"transmitter_{MOCK_TRANSMITTER_SERIAL}_")
    ]

    assert len(transmitter_entities) == 2
    unique_ids = {entity.unique_id for entity in transmitter_entities}
    assert f"transmitter_{MOCK_TRANSMITTER_SERIAL}_last_button" in unique_ids
    assert f"transmitter_{MOCK_TRANSMITTER_SERIAL}_battery_warning" in unique_ids


async def test_neo_sensor_entities_have_unique_ids_from_setup(
    hass: HomeAssistant,
) -> None:
    """Neo sensor entities registered during setup use device-based unique IDs."""
    entry = _entry_with_subentries(
        _neo_sensor_device_record(
            title="Neo Sensor",
            capabilities=NEO_SENSOR_CAPABILITIES,
        )
    )
    await async_setup_easywave_entry(hass, entry)

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    sensor_entities = [
        entity
        for entity in entities
        if entity.unique_id
        and entity.unique_id.startswith(f"neo_sensor_{MOCK_NEO_SENSOR_SERIAL}_")
    ]

    assert len(sensor_entities) == 2
    unique_ids = {entity.unique_id for entity in sensor_entities}
    assert f"neo_sensor_{MOCK_NEO_SENSOR_SERIAL}_temperature" in unique_ids
    assert f"neo_sensor_{MOCK_NEO_SENSOR_SERIAL}_humidity" in unique_ids
