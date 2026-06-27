"""Tests for the nexia sensor platform."""

from nexia.home import NexiaHome

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import setup_integration


async def test_create_sensors(hass: HomeAssistant, patch_nexia_home: NexiaHome) -> None:
    """Test creation of sensors."""

    await setup_integration(hass, patch_nexia_home)

    state = hass.states.get("sensor.nick_office_nick_office_temperature")
    assert state is not None
    assert round(float(state.state)) == 23

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "device_class": "temperature",
        "friendly_name": "Nick Office Temperature",
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("sensor.nick_office_nick_office_zone_setpoint_status")
    assert state is not None
    assert state.state == "Permanent Hold"
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Nick Office Zone setpoint status",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("sensor.nick_office_nick_office_zone_status")
    assert state is not None
    assert state.state == "Relieving Air"

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Nick Office Zone status",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("sensor.master_suite_air_cleaner_mode")
    assert state is not None
    assert state.state == "auto"

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Master Suite Air cleaner mode",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("sensor.master_suite_current_compressor_speed")
    assert state is not None
    assert round(float(state.state)) == 69

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Master Suite Current compressor speed",
        "unit_of_measurement": PERCENTAGE,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("sensor.master_suite_outdoor_temperature")
    assert state is not None
    assert round(float(state.state), 1) == 30.6

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "device_class": "temperature",
        "friendly_name": "Master Suite Outdoor temperature",
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("sensor.master_suite_humidity")
    assert state is not None
    assert state.state == "52.0"

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "device_class": "humidity",
        "friendly_name": "Master Suite Humidity",
        "unit_of_measurement": PERCENTAGE,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("sensor.master_suite_requested_compressor_speed")
    assert state is not None
    assert state.state == "69.0"

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Master Suite Requested compressor speed",
        "unit_of_measurement": PERCENTAGE,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )

    state = hass.states.get("sensor.master_suite_system_status")
    assert state is not None
    assert state.state == "Cooling"

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "friendly_name": "Master Suite System status",
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    assert all(
        state.attributes[key] == value for key, value in expected_attributes.items()
    )


async def test_room_iq_sensors(
    hass: HomeAssistant,
    patch_nexia_home: NexiaHome,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test NexiaRoomIQSensor."""

    config_entry = await setup_integration(hass, patch_nexia_home)

    # Verify disabled by default
    assert patch_nexia_home.any_room_iq_monitors() is False
    state = hass.states.get("sensor.zone3_zone3_roomiq_temperature")
    assert state is None

    # Enable all disabled entities
    for entry in entity_registry.entities.values():
        if entry.disabled_by is not None:
            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.zone3_zone3_roomiq_temperature")
    assert state is not None

    # Verify embedded RoomIQ sensor shows thermostat's model and firmware version
    entry = entity_registry.async_get(state.entity_id)
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.model == "XL1050"
    assert device.sw_version == "5.9.1"

    # Verify states
    assert state.state == "25.0"
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert state.attributes["friendly_name"] == "Zone3 RoomIQ temperature"
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS

    state = hass.states.get("sensor.zone3_zone3_roomiq_humidity")
    assert state is not None
    assert state.state == "45"
    assert state.attributes["device_class"] == SensorDeviceClass.HUMIDITY
    assert state.attributes["friendly_name"] == "Zone3 RoomIQ humidity"
    assert state.attributes["unit_of_measurement"] == PERCENTAGE

    state = hass.states.get("sensor.zone3_zone3_roomiq_battery")
    assert state is None

    state = hass.states.get("sensor.upstairs_upstairs_roomiq_temperature")
    assert state is not None

    # Verify online RoomIQ sensor shows no model nor firmware version
    entry = entity_registry.async_get(state.entity_id)
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.model is None
    assert device.sw_version is None

    # Verify states
    assert state.state == "22.5"
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert state.attributes["friendly_name"] == "Upstairs RoomIQ temperature"
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS

    state = hass.states.get("sensor.upstairs_upstairs_roomiq_humidity")
    assert state is not None
    assert state.state == "45"
    assert state.attributes["device_class"] == SensorDeviceClass.HUMIDITY
    assert state.attributes["friendly_name"] == "Upstairs RoomIQ humidity"
    assert state.attributes["unit_of_measurement"] == PERCENTAGE

    state = hass.states.get("sensor.upstairs_upstairs_roomiq_battery")
    assert state is not None
    assert state.state == "93"
    assert state.attributes["device_class"] == SensorDeviceClass.BATTERY
    assert state.attributes["friendly_name"] == "Upstairs RoomIQ battery"
    assert state.attributes["unit_of_measurement"] == PERCENTAGE

    state = hass.states.get("sensor.downstairs_downstairs_roomiq_temperature")
    assert state is not None
    assert state.state == "unavailable"

    # Verify sensors are registered
    assert patch_nexia_home.any_room_iq_monitors() is True

    # Unload should trigger registration removal
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert patch_nexia_home.any_room_iq_monitors() is False
