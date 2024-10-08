"""Test the Trend integration."""

from homeassistant.components.trend.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import ComponentSetup

from tests.common import MockConfigEntry


async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test setting up and removing a config entry."""
    trend_entity_id = "binary_sensor.my_trend"

    # Set up the config entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(trend_entity_id) is not None

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(trend_entity_id) is None
    assert entity_registry.async_get(trend_entity_id) is None


async def test_reload_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_component: ComponentSetup,
) -> None:
    """Test config entry reload."""
    await setup_component({})

    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "max_samples": 4.0}
    )

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data == {**config_entry.data, "max_samples": 4.0}


async def test_device_cleaning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Trend."""

    # Source entity device config entry
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)

    # Device entry of the source entity
    source_device1_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("sensor", "identifier_test1")},
        connections={("mac", "30:31:32:33:34:01")},
    )

    # Source entity registry
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device1_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    # Configure the configuration entry for Trend
    trend_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Trend",
            "entity_id": "sensor.test_source",
            "invert": False,
        },
        title="Trend",
    )
    trend_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the trend sensor
    trend_entity = entity_registry.async_get("binary_sensor.trend")
    assert trend_entity is not None
    assert trend_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to Trend config entry
    device_registry.async_get_or_create(
        config_entry_id=trend_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=trend_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, two devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        trend_config_entry.entry_id
    )
    assert len(devices_before_reload) == 3

    # Config entry reload
    await hass.config_entries.async_reload(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the trend sensor after reload
    trend_entity = entity_registry.async_get("binary_sensor.trend")
    assert trend_entity is not None
    assert trend_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        trend_config_entry.entry_id
    )
    assert len(devices_after_reload) == 1
