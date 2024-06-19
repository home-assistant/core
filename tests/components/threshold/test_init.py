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
