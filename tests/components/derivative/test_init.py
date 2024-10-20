"""Test the Derivative integration."""

import pytest

from homeassistant.components.derivative.const import DOMAIN
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
    derivative_entity_id = f"{platform}.my_derivative"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.input",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My derivative",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(derivative_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(derivative_entity_id)
    assert state.state == "0.0"
    assert "unit_of_measurement" not in state.attributes
    assert state.attributes["source"] == "sensor.input"

    hass.states.async_set(input_sensor_entity_id, 10, {"unit_of_measurement": "dog"})
    hass.states.async_set(input_sensor_entity_id, 11, {"unit_of_measurement": "dog"})
    await hass.async_block_till_done()
    state = hass.states.get(derivative_entity_id)
    assert state.state != "0"
    assert state.attributes["unit_of_measurement"] == "kdog/min"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(derivative_entity_id) is None
    assert entity_registry.async_get(derivative_entity_id) is None


async def test_device_cleaning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Derivative."""

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

    # Configure the configuration entry for Derivative
    derivative_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Derivative",
            "round": 1.0,
            "source": "sensor.test_source",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="Derivative",
    )
    derivative_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the derivative sensor
    derivative_entity = entity_registry.async_get("sensor.derivative")
    assert derivative_entity is not None
    assert derivative_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to Derivative config entry
    device_registry.async_get_or_create(
        config_entry_id=derivative_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=derivative_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, two devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        derivative_config_entry.entry_id
    )
    assert len(devices_before_reload) == 3

    # Config entry reload
    await hass.config_entries.async_reload(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the derivative sensor after reload
    derivative_entity = entity_registry.async_get("sensor.derivative")
    assert derivative_entity is not None
    assert derivative_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        derivative_config_entry.entry_id
    )
    assert len(devices_after_reload) == 1
