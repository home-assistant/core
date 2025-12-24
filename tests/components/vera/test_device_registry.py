"""Tests for Vera device registry."""

from unittest.mock import MagicMock

import pyvera as pv

from homeassistant.components.vera import CONF_CONTROLLER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import ComponentFactory, ConfigSource, new_simple_controller_config


async def test_hub_device_created(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    vera_component_factory: ComponentFactory,
) -> None:
    """Test that a hub device is created in the device registry."""
    vera_device1: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device1.device_id = 1
    vera_device1.vera_device_id = vera_device1.device_id
    vera_device1.name = "test_sensor"
    vera_device1.is_tripped = False
    vera_device1.category = pv.CATEGORY_SENSOR

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://127.0.0.1:111"},
            config_source=ConfigSource.CONFIG_FLOW,
            serial_number="test_serial_123",
            devices=(vera_device1,),
        ),
    )

    # Verify the hub device was created
    hub_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "test_serial_123")}
    )
    assert hub_device is not None
    assert hub_device.manufacturer == "Vera Control, Ltd"
    assert hub_device.model == "Vera Controller"
    assert "Vera" in hub_device.name
    assert hub_device.configuration_url == "http://127.0.0.1:111"


async def test_entity_device_linked_to_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    vera_component_factory: ComponentFactory,
) -> None:
    """Test that entity devices are linked to the hub via via_device."""
    vera_device1: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device1.device_id = 1
    vera_device1.vera_device_id = vera_device1.device_id
    vera_device1.name = "test_sensor"
    vera_device1.is_tripped = False
    vera_device1.category = pv.CATEGORY_SENSOR

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://127.0.0.1:111"},
            config_source=ConfigSource.CONFIG_FLOW,
            serial_number="test_serial_123",
            devices=(vera_device1,),
        ),
    )

    # Get the hub device
    hub_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "test_serial_123")}
    )
    assert hub_device is not None

    # Get the sensor device
    sensor_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "test_serial_123_1")}
    )
    assert sensor_device is not None
    assert sensor_device.name == "test_sensor"
    assert sensor_device.manufacturer == "Vera"
    assert sensor_device.model == "Sensor"
    assert sensor_device.via_device_id == hub_device.id


async def test_multiple_devices_under_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    vera_component_factory: ComponentFactory,
) -> None:
    """Test that multiple entity devices are properly linked to the same hub."""
    vera_sensor: pv.VeraSensor = MagicMock(spec=pv.VeraSensor)
    vera_sensor.device_id = 1
    vera_sensor.vera_device_id = vera_sensor.device_id
    vera_sensor.name = "temperature_sensor"
    vera_sensor.category = pv.CATEGORY_TEMPERATURE_SENSOR
    vera_sensor.temperature = 22.5

    vera_switch: pv.VeraSwitch = MagicMock(spec=pv.VeraSwitch)
    vera_switch.device_id = 2
    vera_switch.vera_device_id = vera_switch.device_id
    vera_switch.name = "living_room_light"
    vera_switch.category = pv.CATEGORY_SWITCH
    vera_switch.is_switched_on = MagicMock(return_value=False)

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://192.168.1.100:3480"},
            config_source=ConfigSource.CONFIG_FLOW,
            serial_number="hub_12345",
            devices=(vera_sensor, vera_switch),
        ),
    )

    # Get the hub device
    hub_device = device_registry.async_get_device(identifiers={(DOMAIN, "hub_12345")})
    assert hub_device is not None

    # Get the sensor device
    sensor_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "hub_12345_1")}
    )
    assert sensor_device is not None
    assert sensor_device.via_device_id == hub_device.id

    # Get the switch device
    switch_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "hub_12345_2")}
    )
    assert switch_device is not None
    assert switch_device.via_device_id == hub_device.id
