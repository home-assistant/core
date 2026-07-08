"""Tests to ensure all Easywave entities have valid unique IDs."""

from homeassistant.components.easywave.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_ID,
    MOCK_NEO_SENSOR_SERIAL,
    MOCK_TRANSMITTER_SERIAL,
    _devices_options,
    _neo_sensor_device_record,
    _transmitter_device_record,
    async_setup_easywave_entry,
)

from tests.common import MockConfigEntry

NEO_SENSOR_CAPABILITIES = (1 << 4) | (1 << 5)


async def test_transmitter_entities_have_unique_ids_from_setup(
    hass: HomeAssistant,
) -> None:
    """Transmitter entities registered during setup use device-based unique IDs."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(_transmitter_device_record(title="Test Transmitter")),
    )
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
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options=_devices_options(
            _neo_sensor_device_record(
                title="Neo Sensor",
                capabilities=NEO_SENSOR_CAPABILITIES,
            )
        ),
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
