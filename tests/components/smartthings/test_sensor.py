"""Test for the SmartThings sensors platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import ATTRIBUTES, CAPABILITIES, Attribute, Capability

from homeassistant.components.sensor import (
    DEVICE_CLASSES,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASSES,
)
from homeassistant.components.smartthings import sensor
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_mapping_integrity() -> None:
    """Test ensures the map dicts have proper integrity."""
    for capability, maps in sensor.CAPABILITY_TO_SENSORS.items():
        assert capability in CAPABILITIES, capability
        for sensor_map in maps:
            assert sensor_map.attribute in ATTRIBUTES, sensor_map.attribute
            if sensor_map.device_class:
                assert (
                    sensor_map.device_class in DEVICE_CLASSES
                ), sensor_map.device_class
            if sensor_map.state_class:
                assert sensor_map.state_class in STATE_CLASSES, sensor_map.state_class


async def test_entity_state(hass: HomeAssistant, device_factory) -> None:
    """Tests the state attributes properly match the sensor types."""
    device = device_factory("Sensor 1", [Capability.battery], {Attribute.battery: 100})
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    state = hass.states.get("sensor.sensor_1_battery")
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{device.label} Battery"


async def test_entity_three_axis_state(hass: HomeAssistant, device_factory) -> None:
    """Tests the state attributes properly match the three axis types."""
    device = device_factory(
        "Three Axis", [Capability.three_axis], {Attribute.three_axis: [100, 75, 25]}
    )
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    state = hass.states.get("sensor.three_axis_x_coordinate")
    assert state.state == "100"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{device.label} X Coordinate"
    state = hass.states.get("sensor.three_axis_y_coordinate")
    assert state.state == "75"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{device.label} Y Coordinate"
    state = hass.states.get("sensor.three_axis_z_coordinate")
    assert state.state == "25"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{device.label} Z Coordinate"


async def test_entity_three_axis_invalid_state(
    hass: HomeAssistant, device_factory
) -> None:
    """Tests the state attributes properly match the three axis types."""
    device = device_factory(
        "Three Axis", [Capability.three_axis], {Attribute.three_axis: []}
    )
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    state = hass.states.get("sensor.three_axis_x_coordinate")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.three_axis_y_coordinate")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.three_axis_z_coordinate")
    assert state.state == STATE_UNKNOWN


async def test_entity_and_device_attributes(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "Sensor 1",
        [Capability.battery],
        {
            Attribute.battery: 100,
            Attribute.mnmo: "123",
            Attribute.mnmn: "Generic manufacturer",
            Attribute.mnhw: "v4.56",
            Attribute.mnfv: "v7.89",
        },
    )
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Act
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    # Assert
    entry = entity_registry.async_get("sensor.sensor_1_battery")
    assert entry
    assert entry.unique_id == f"{device.device_id}.{Attribute.battery}"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC
    entry = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == "123"
    assert entry.manufacturer == "Generic manufacturer"
    assert entry.hw_version == "v4.56"
    assert entry.sw_version == "v7.89"


async def test_energy_sensors_for_switch_device(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "Switch_1",
        [Capability.switch, Capability.power_meter, Capability.energy_meter],
        {
            Attribute.switch: "off",
            Attribute.power: 355,
            Attribute.energy: 11.422,
            Attribute.mnmo: "123",
            Attribute.mnmn: "Generic manufacturer",
            Attribute.mnhw: "v4.56",
            Attribute.mnfv: "v7.89",
        },
    )
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Act
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    # Assert
    state = hass.states.get("sensor.switch_1_energy_meter")
    assert state
    assert state.state == "11.422"
    entry = entity_registry.async_get("sensor.switch_1_energy_meter")
    assert entry
    assert entry.unique_id == f"{device.device_id}.{Attribute.energy}"
    assert entry.entity_category is None
    entry = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == "123"
    assert entry.manufacturer == "Generic manufacturer"
    assert entry.hw_version == "v4.56"
    assert entry.sw_version == "v7.89"

    state = hass.states.get("sensor.switch_1_power_meter")
    assert state
    assert state.state == "355"
    entry = entity_registry.async_get("sensor.switch_1_power_meter")
    assert entry
    assert entry.unique_id == f"{device.device_id}.{Attribute.power}"
    assert entry.entity_category is None
    entry = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == "123"
    assert entry.manufacturer == "Generic manufacturer"
    assert entry.hw_version == "v4.56"
    assert entry.sw_version == "v7.89"


async def test_power_consumption_sensor(hass: HomeAssistant, device_factory) -> None:
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "refrigerator",
        [Capability.power_consumption_report],
        {
            Attribute.power_consumption: {
                "energy": 1412002,
                "deltaEnergy": 25,
                "power": 109,
                "powerEnergy": 24.304498331745464,
                "persistedEnergy": 0,
                "energySaved": 0,
                "start": "2021-07-30T16:45:25Z",
                "end": "2021-07-30T16:58:33Z",
            },
            Attribute.mnmo: "123",
            Attribute.mnmn: "Generic manufacturer",
            Attribute.mnhw: "v4.56",
            Attribute.mnfv: "v7.89",
        },
    )
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Act
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    # Assert
    state = hass.states.get("sensor.refrigerator_energy")
    assert state
    assert state.state == "1412.002"
    entry = entity_registry.async_get("sensor.refrigerator_energy")
    assert entry
    assert entry.unique_id == f"{device.device_id}.energy_meter"
    entry = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == "123"
    assert entry.manufacturer == "Generic manufacturer"
    assert entry.hw_version == "v4.56"
    assert entry.sw_version == "v7.89"

    state = hass.states.get("sensor.refrigerator_power")
    assert state
    assert state.state == "109"
    assert state.attributes["power_consumption_start"] == "2021-07-30T16:45:25Z"
    assert state.attributes["power_consumption_end"] == "2021-07-30T16:58:33Z"
    entry = entity_registry.async_get("sensor.refrigerator_power")
    assert entry
    assert entry.unique_id == f"{device.device_id}.power_meter"
    entry = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == "123"
    assert entry.manufacturer == "Generic manufacturer"
    assert entry.hw_version == "v4.56"
    assert entry.sw_version == "v7.89"

    device = device_factory(
        "vacuum",
        [Capability.power_consumption_report],
        {
            Attribute.power_consumption: {},
            Attribute.mnmo: "123",
            Attribute.mnmn: "Generic manufacturer",
            Attribute.mnhw: "v4.56",
            Attribute.mnfv: "v7.89",
        },
    )
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Act
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    # Assert
    state = hass.states.get("sensor.vacuum_energy")
    assert state
    assert state.state == "unknown"
    entry = entity_registry.async_get("sensor.vacuum_energy")
    assert entry
    assert entry.unique_id == f"{device.device_id}.energy_meter"
    entry = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == "123"
    assert entry.manufacturer == "Generic manufacturer"
    assert entry.hw_version == "v4.56"
    assert entry.sw_version == "v7.89"


async def test_update_from_signal(hass: HomeAssistant, device_factory) -> None:
    """Test the binary_sensor updates when receiving a signal."""
    # Arrange
    device = device_factory("Sensor 1", [Capability.battery], {Attribute.battery: 100})
    await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    device.status.apply_attribute_update(
        "main", Capability.battery, Attribute.battery, 75
    )
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("sensor.sensor_1_battery")
    assert state is not None
    assert state.state == "75"


async def test_unload_config_entry(hass: HomeAssistant, device_factory) -> None:
    """Test the binary_sensor is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory("Sensor 1", [Capability.battery], {Attribute.battery: 100})
    config_entry = await setup_platform(hass, SENSOR_DOMAIN, devices=[device])
    config_entry.state = ConfigEntryState.LOADED
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    # Assert
    assert hass.states.get("sensor.sensor_1_battery").state == STATE_UNAVAILABLE
