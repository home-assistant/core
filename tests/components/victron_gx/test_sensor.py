"""Tests for Victron GX MQTT sensors."""

from unittest.mock import MagicMock

from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.components.victron_gx.sensor import VictronSensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_platform,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import DeviceInfo

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

    # Inject a system metric first so the gateway device (system_0) is registered
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/system/0/SystemState/State",
        '{"value": 1}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    # Verify system device has no via_device (it IS the gateway)
    system_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_system_0")}
    )
    assert system_device is not None
    assert system_device.via_device_id is None

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

    # Exactly two entities are expected: system state + battery current
    assert len(entities) == 2
    entity = next(e for e in entities if e.entity_id == "sensor.battery_dc_bus_current")
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
    # Verify battery device has via_device pointing to system_0 (gateway)
    assert device.via_device_id == system_device.id

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


async def test_victron_main_topic_sensor(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor with main_topic=True keeps translation key and device name."""
    victron_hub, mock_config_entry = init_integration

    # Multi RS MPPT MppOperationMode is a main_topic metric
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/multi/0/Pv/1/MppOperationMode",
        '{"value": 2}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_multi_0_multi_mppt_1_state"
    assert entity.translation_key == "multi_mppt_mpptnumber_state"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "mppt_active"
    # Entity uses device name only (no separate entity name)
    assert state.attributes["friendly_name"] == "Multi RS Solar"


async def test_native_unit_of_measurement_cost_metric(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test native_unit_of_measurement returns currency for COST metric type."""
    victron_hub, mock_config_entry = init_integration

    hass.config.currency = "USD"

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/Session/Cost",
        '{"value": 12.34}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entity = next(
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if e.translation_key == "evcharger_session_cost"
    )

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes["unit_of_measurement"] == "USD"
    assert state.state == "12.34"


async def test_native_unit_of_measurement_with_device_class(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test native_unit_of_measurement returns unit for metrics with device class."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 10.5}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entity = next(
        (
            e
            for e in er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
            if e.entity_id == "sensor.battery_dc_bus_current"
        ),
        None,
    )
    assert entity is not None

    platforms = entity_platform.async_get_platforms(hass, DOMAIN)
    sensor_platform = next(p for p in platforms if p.domain == "sensor")
    actual_entity = next(
        (
            e
            for e in sensor_platform.entities.values()
            if e.entity_id == entity.entity_id
        ),
        None,
    )

    assert actual_entity is not None
    assert actual_entity.native_unit_of_measurement == "A"


async def test_native_unit_of_measurement_special_unit(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test native_unit_of_measurement returns special units like %."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Soc",
        '{"value": 85}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entity = next(
        (
            e
            for e in er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
            if e.unit_of_measurement == "%"
        ),
        None,
    )
    assert entity is not None

    platforms = entity_platform.async_get_platforms(hass, DOMAIN)
    sensor_platform = next(p for p in platforms if p.domain == "sensor")
    actual_entity = next(
        (
            e
            for e in sensor_platform.entities.values()
            if e.entity_id == entity.entity_id
        ),
        None,
    )

    assert actual_entity is not None
    assert actual_entity.native_unit_of_measurement == "%"


async def test_native_unit_of_measurement_return_none(
    hass: HomeAssistant,
) -> None:
    """Test native_unit_of_measurement returns None when no conditions are met."""
    mock_device = MagicMock()
    mock_metric = MagicMock()
    mock_metric.metric_type = MagicMock()
    mock_metric.unit_of_measurement = "arbitrary_unit"
    mock_metric.precision = 0
    mock_metric.generic_short_id = "test_metric"
    mock_metric.key_values = {}
    mock_metric.main_topic = False
    mock_metric.unique_id = "test_unique_id"

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "test_device")},
        manufacturer="Victron Energy",
        model="Test",
        name="Test Device",
    )

    sensor = VictronSensor(mock_device, mock_metric, device_info, "installation_123")
    sensor.hass = hass
    sensor._attr_device_class = None

    assert sensor.native_unit_of_measurement is None
