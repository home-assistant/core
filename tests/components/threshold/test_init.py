"""Test the Min/Max integration."""

import pytest

from homeassistant.components.threshold.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ["binary_sensor"])
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    hass.states.async_set("sensor.input", "-10")

    input_sensor = "sensor.input"

    threshold_entity_id = f"{platform}.input_threshold"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor,
            "hysteresis": 0.0,
            "lower": -2.0,
            "name": "Input threshold",
            "upper": None,
        },
        title="Input threshold",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(threshold_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(threshold_entity_id)
    assert state
    assert state.state == "on"
    assert state.attributes["entity_id"] == input_sensor
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["lower"] == -2.0
    assert state.attributes["position"] == "below"
    assert state.attributes["sensor_value"] == -10.0
    assert state.attributes["type"] == "lower"
    assert state.attributes["upper"] is None

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(threshold_entity_id) is None
    assert entity_registry.async_get(threshold_entity_id) is None


@pytest.mark.parametrize("platform", ["sensor"])
async def test_entry_changed(hass: HomeAssistant, platform) -> None:
    """Test reconfiguring."""

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    def _create_mock_entity(domain: str, name: str) -> er.RegistryEntry:
        config_entry = MockConfigEntry(
            data={},
            domain="test",
            title=f"{name}",
        )
        config_entry.add_to_hass(hass)
        device_entry = device_registry.async_get_or_create(
            identifiers={("test", name)}, config_entry_id=config_entry.entry_id
        )
        return entity_registry.async_get_or_create(
            domain, "test", name, suggested_object_id=name, device_id=device_entry.id
        )

    def _get_device_config_entries(entry: er.RegistryEntry) -> set[str]:
        assert entry.device_id
        device = device_registry.async_get(entry.device_id)
        assert device
        return device.config_entries

    # Set up entities, with backing devices and config entries
    run1_entry = _create_mock_entity("sensor", "initial")
    run2_entry = _create_mock_entity("sensor", "changed")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": "sensor.initial",
            "hysteresis": 0.0,
            "lower": -2.0,
            "name": "My threshold",
            "upper": None,
        },
        title="My integration",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.entry_id in _get_device_config_entries(run1_entry)
    assert config_entry.entry_id not in _get_device_config_entries(run2_entry)

    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "entity_id": "sensor.changed"}
    )
    await hass.async_block_till_done()

    # Check that the config entry association has updated
    assert config_entry.entry_id not in _get_device_config_entries(run1_entry)
    assert config_entry.entry_id in _get_device_config_entries(run2_entry)


async def test_device_cleaning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Threshold."""

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

    # Configure the configuration entry for Threshold
    threshold_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": "sensor.test_source",
            "hysteresis": 0.0,
            "lower": -2.0,
            "name": "Threshold",
            "upper": None,
        },
        title="Threshold",
    )
    threshold_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(threshold_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the threshold sensor
    threshold_entity = entity_registry.async_get("binary_sensor.threshold")
    assert threshold_entity is not None
    assert threshold_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to Threshold config entry
    device_registry.async_get_or_create(
        config_entry_id=threshold_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=threshold_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, two devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        threshold_config_entry.entry_id
    )
    assert len(devices_before_reload) == 3

    # Config entry reload
    await hass.config_entries.async_reload(threshold_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the threshold sensor after reload
    threshold_entity = entity_registry.async_get("binary_sensor.threshold")
    assert threshold_entity is not None
    assert threshold_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        threshold_config_entry.entry_id
    )
    assert len(devices_after_reload) == 1
