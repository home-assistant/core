"""Test the Integration - Riemann sum integral integration."""

import pytest

from homeassistant.components.integration.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ["sensor"])
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    input_sensor_entity_id = "sensor.input"
    integration_entity_id = f"{platform}.my_integration"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "method": "trapezoidal",
            "name": "My integration",
            "round": 1.0,
            "source": "sensor.input",
            "unit_prefix": "k",
            "unit_time": "min",
            "max_sub_interval": {"minutes": 1},
        },
        title="My integration",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(integration_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(integration_entity_id)
    assert state.state == "unknown"
    assert "unit_of_measurement" not in state.attributes
    assert state.attributes["source"] == "sensor.input"

    hass.states.async_set(input_sensor_entity_id, 10, {"unit_of_measurement": "cat"})
    hass.states.async_set(input_sensor_entity_id, 11, {"unit_of_measurement": "cat"})
    await hass.async_block_till_done()
    state = hass.states.get(integration_entity_id)
    assert state.state != "unknown"
    assert state.attributes["unit_of_measurement"] == "kcatmin"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(integration_entity_id) is None
    assert entity_registry.async_get(integration_entity_id) is None


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
    input_entry = _create_mock_entity("sensor", "input")
    valid_entry = _create_mock_entity("sensor", "valid")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "method": "left",
            "name": "My integration",
            "source": "sensor.input",
            "unit_time": "min",
        },
        title="My integration",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.entry_id in _get_device_config_entries(input_entry)
    assert config_entry.entry_id not in _get_device_config_entries(valid_entry)

    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "source": "sensor.valid"}
    )
    await hass.async_block_till_done()

    # Check that the config entry association has updated
    assert config_entry.entry_id not in _get_device_config_entries(input_entry)
    assert config_entry.entry_id in _get_device_config_entries(valid_entry)
