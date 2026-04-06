"""Tests for Victron GX MQTT sensors."""

from __future__ import annotations

from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry


async def test_victron_battery_sensor(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test SENSOR MetricKind - battery current sensor is created and updated."""
    victron_hub, mock_config_entry = init_integration

    # Inject a sensor metric (battery current)
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 10.5}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    # Verify entity was created by checking entity registry
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Exactly one entity is expected for this injected metric.
    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == "sensor.battery_dc_bus_current"
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_battery_0_battery_current"
    assert entity.original_device_class is SensorDeviceClass.CURRENT
    assert entity.unit_of_measurement == "A"
    assert entity.translation_key == "battery_current"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "10.5"
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["device_class"] == "current"
    assert state.attributes["unit_of_measurement"] == "A"

    # Verify device info was registered correctly
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_battery_0")}
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"
    assert device.name == "Battery"

    # Update the same metric to exercise the entity update callback path.
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 11.2}',
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "11.2"


async def test_victron_enum_sensor(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sensor with VictronEnum value normalizes to enum id."""
    victron_hub, _mock_config_entry = init_integration

    # SystemState/State produces a VictronEnum (State enum)
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/system/0/SystemState/State",
        '{"value": 1}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.victron_venus_system_state")
    assert state is not None
    # Value 1 maps to State.LOW_POWER with id="low_power"
    assert state.state == "low_power"

    # Verify system device has no via_device (it IS the gateway)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_system_0")}
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"
    assert device.via_device_id is None
