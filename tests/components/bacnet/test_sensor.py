"""Tests for the BACnet sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.bacnet.bacnet_client import (
    BACnetDeviceInfo,
    BACnetObjectInfo,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MOCK_DEVICE_KEY, create_mock_hub_config_entry, init_integration


async def test_analog_sensors_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that analog sensors are created for analog BACnet objects."""
    await init_integration(hass)

    # Zone Temperature (analog-input,0) - 72.5°F converted to °C by HA
    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    assert float(state.state) == 22.5

    # Outside Air Temperature (analog-input,1) - 55.0°F converted to °C
    state = hass.states.get("sensor.test_hvac_controller_outside_air_temperature")
    assert state is not None
    # 55°F = 12.7778°C (HA stores the full precision)
    assert abs(float(state.state) - 12.7778) < 0.01

    # Zone Humidity (analog-input,2) - 45% stays as 45%
    state = hass.states.get("sensor.test_hvac_controller_zone_humidity")
    assert state is not None
    assert state.state == "45.0"


async def test_analog_sensor_device_class(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that BACnet units map to correct device classes."""
    await init_integration(hass)

    # Temperature sensor should have temperature device class
    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE

    # Humidity sensor should have humidity device class
    state = hass.states.get("sensor.test_hvac_controller_zone_humidity")
    assert state is not None
    assert state.attributes.get("device_class") == SensorDeviceClass.HUMIDITY
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_multistate_sensor_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that multi-state sensors show text from stateText mapping."""
    await init_integration(hass)

    # Operating Mode (multi-state-input,0) - value 2 maps to "Heating"
    state = hass.states.get("sensor.test_hvac_controller_operating_mode")
    assert state is not None
    assert state.state == "Heating"
    assert state.attributes.get("device_class") == SensorDeviceClass.ENUM
    assert state.attributes.get("options") == ["Off", "Heating", "Cooling", "Auto"]


async def test_sensor_count(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test the correct number of sensors are created."""
    await init_integration(hass)

    sensor_states = hass.states.async_entity_ids("sensor")
    # We expect 5 sensors:
    # analog-input,0 (Zone Temp), analog-input,1 (OAT), analog-input,2 (Humidity),
    # analog-value,0 (Setpoint), multi-state-input,0 (Operating Mode)
    assert len(sensor_states) == 5


async def test_device_info_no_suggested_area(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that device_info does not include suggested_area."""
    await init_integration(hass)

    # Get entity registry and pick a sensor
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get("sensor.test_hvac_controller_zone_temperature")
    assert entity is not None

    # Get device registry and check the device
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entity.device_id)
    assert device is not None

    # If suggested_area was set during device creation, it would populate area_id.
    # Verify no area was assigned (meaning no suggested_area in device_info).
    assert device.area_id is None


async def test_multistate_sensor_without_state_text(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that multi-state sensor without state_text shows raw value without ENUM class."""
    mock_bacnet_client.get_device_objects.return_value = [
        BACnetObjectInfo(
            object_type="multi-state-input",
            object_instance=0,
            object_name="Operating Mode",
            present_value=2,
            units="",
        ),
    ]

    await init_integration(hass)

    state = hass.states.get("sensor.test_hvac_controller_operating_mode")
    assert state is not None
    assert state.state == "2"
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("options") is None


async def test_analog_sensor_string_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test analog sensor handles string values that can be parsed as float."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Set a string value
    coordinator.data.values["analog-input,0"] = "72.5"
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    # Should parse string to float (and HA may convert units)
    assert state.state != "unknown"


async def test_analog_sensor_invalid_string_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test analog sensor handles unparsable string values."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator.data.values["analog-input,0"] = "not-a-number"
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    assert state.state == "unknown"


async def test_analog_sensor_none_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test analog sensor handles None value."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator.data.values["analog-input,0"] = None
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    assert state.state == "unknown"


async def test_analog_sensor_unexpected_type_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test analog sensor handles unexpected value types (e.g. list)."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Set a list value (unexpected type that's not int, float, str, or None)
    coordinator.data.values["analog-input,0"] = [1, 2, 3]
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    assert state.state == "unknown"


async def test_multistate_sensor_updated_state_text(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test multi-state sensor updates options when state_text changes."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Update the object's state_text via re-discovery simulation
    for obj in coordinator.data.objects:
        if obj.object_type == "multi-state-input" and obj.object_instance == 0:
            obj.state_text = ["Off", "Heating", "Cooling", "Auto", "Emergency"]
            break

    coordinator.data.values["multi-state-input,0"] = 5
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_hvac_controller_operating_mode")
    assert state is not None
    assert state.state == "Emergency"

    # Trigger a second update so the updated options list is written to state
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_hvac_controller_operating_mode")
    assert state.attributes.get("options") == [
        "Off",
        "Heating",
        "Cooling",
        "Auto",
        "Emergency",
    ]


async def test_sensor_selected_objects_filter(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that only selected objects create sensor entities when filter is set."""
    entry = create_mock_hub_config_entry(selected_objects=["analog-input,0"])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]
    coordinator._initial_setup_done = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Only analog-input,0 should be created
    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None

    state = hass.states.get("sensor.test_hvac_controller_outside_air_temperature")
    assert state is None


async def test_entity_no_object_name(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test entity falls back to type+instance when object_name is empty."""
    mock_bacnet_client.get_device_objects.return_value = [
        BACnetObjectInfo(
            object_type="analog-input",
            object_instance=5,
            object_name="",
            present_value=10.0,
            units="percent",
        ),
    ]

    await init_integration(hass)

    # Name fallback: "analog-input 5"
    state = hass.states.get("sensor.test_hvac_controller_analog_input_5")
    assert state is not None


async def test_entity_with_mac_address(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test device info includes MAC address connection when available."""
    # Replace device info with one that includes mac_address
    device_info = BACnetDeviceInfo(
        device_id=1234,
        address="192.168.1.100:47808",
        name="Test HVAC Controller",
        vendor_name="Test Vendor",
        model_name="Model X",
        firmware_revision="1.0.0",
        mac_address="00:11:22:33:44:55",
    )
    mock_bacnet_client.discover_device_at_address.return_value = device_info

    # Use targeted discovery side_effect that returns the updated device_info
    async def _mock_discover(
        timeout: int = 5,
        low_limit: int | None = None,
        high_limit: int | None = None,
    ) -> list:
        if low_limit is not None:
            if low_limit <= device_info.device_id <= (high_limit or low_limit):
                return [device_info]
            return []
        return []

    mock_bacnet_client.discover_devices = AsyncMock(side_effect=_mock_discover)

    await init_integration(hass)

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get("sensor.test_hvac_controller_zone_temperature")
    assert entity is not None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entity.device_id)
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "00:11:22:33:44:55") in device.connections


async def test_entity_current_object_info_data_none(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test _current_object_info returns None when coordinator data is None."""
    entry = await init_integration(hass)

    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Force coordinator data to None
    coordinator.data = None
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_hvac_controller_zone_temperature")
    assert state is not None
    assert state.state == "unknown"


async def test_entity_current_object_info_not_found(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test _current_object_info returns None when object is removed from data."""
    entry = await init_integration(hass)

    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    # Remove all objects but keep data
    coordinator.data.objects = []
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Multi-state sensor that uses _current_object_info for state_text lookup
    state = hass.states.get("sensor.test_hvac_controller_operating_mode")
    assert state is not None
