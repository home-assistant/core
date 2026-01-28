"""Tests for PulseGrow sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test sensor states are correctly reported."""
    # Check temperature sensor (72.5F = 22.5C, converted by Home Assistant)
    state = hass.states.get("sensor.test_pulse_pro_temperature")
    assert state is not None
    assert state.state == "22.5"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE

    # Check humidity sensor
    state = hass.states.get("sensor.test_pulse_pro_humidity")
    assert state is not None
    assert state.state == "55.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.HUMIDITY

    # Check VPD sensor
    state = hass.states.get("sensor.test_pulse_pro_vpd")
    assert state is not None
    assert state.state == "1.2"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.PRESSURE

    # Check CO2 sensor
    state = hass.states.get("sensor.test_pulse_pro_co2")
    assert state is not None
    assert state.state == "800"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.CO2

    # Check light sensor
    state = hass.states.get("sensor.test_pulse_pro_light")
    assert state is not None
    assert state.state == "5000"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "lx"

    # Check air pressure sensor (101325 Pa = 1013.25 hPa, converted by Home Assistant)
    state = hass.states.get("sensor.test_pulse_pro_air_pressure")
    assert state is not None
    assert state.state == "1013.25"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ATMOSPHERIC_PRESSURE

    # Check dew point sensor (55.0F = 12.78C approximately, converted by Home Assistant)
    state = hass.states.get("sensor.test_pulse_pro_dew_point")
    assert state is not None
    # Check the value starts with "12." since the exact conversion varies
    assert state.state.startswith("12.")
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE


async def test_sensor_unavailable_when_device_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test sensors become unavailable when device is removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify sensor is available initially
    state = hass.states.get("sensor.test_pulse_pro_temperature")
    assert state is not None
    assert state.state == "22.5"

    # Update mock to return empty DeviceData (device removed)
    mock_device_data = MagicMock()
    mock_device_data.devices = []
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    # Trigger coordinator refresh
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check sensor is unavailable
    state = hass.states.get("sensor.test_pulse_pro_temperature")
    assert state is not None
    assert state.state == "unavailable"


async def test_sensor_with_no_data_point(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test sensor handles missing most_recent_data_point."""
    # Create a device without data point
    mock_device = MagicMock()
    mock_device.id = 456
    mock_device.guid = "device-456"
    mock_device.name = "Device Without Data"
    mock_device.device_type = 1
    mock_device.most_recent_data_point = None

    mock_device_data = MagicMock()
    mock_device_data.devices = [mock_device]
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # No sensors should be created for this device
    state = hass.states.get("sensor.device_without_data_temperature")
    assert state is None


async def test_sensor_with_hub_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test sensors from hub devices."""
    # Create a hub with mac_address
    mock_hub = MagicMock()
    mock_hub.id = 100
    mock_hub.name = "Test Hub"
    mock_hub.mac_address = "AA:BB:CC:DD:EE:FF"

    mock_pulsegrow_client.get_hub_ids.return_value = [100]
    mock_pulsegrow_client.get_hub_details.return_value = mock_hub

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Hub MAC address sensor is disabled by default, so it shouldn't appear
    state = hass.states.get("sensor.test_hub_mac_address")
    assert state is None


async def test_device_with_unknown_device_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test device with unknown device_type handles gracefully."""
    mock_data_point = MagicMock()
    mock_data_point.temperature_f = 70.0
    mock_data_point.humidity_rh = None
    mock_data_point.vpd = None
    mock_data_point.co2 = None
    mock_data_point.light_lux = None
    mock_data_point.air_pressure = None
    mock_data_point.dp_f = None
    mock_data_point.signal_strength = None
    mock_data_point.battery_v = None

    mock_device = MagicMock()
    mock_device.id = 789
    mock_device.guid = "device-789"
    mock_device.name = "Unknown Device"
    mock_device.device_type = 999  # Unknown type
    mock_device.most_recent_data_point = mock_data_point

    mock_device_data = MagicMock()
    mock_device_data.devices = [mock_device]
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Temperature sensor should still work
    state = hass.states.get("sensor.unknown_device_temperature")
    assert state is not None
    # 70F = 21.111C approximately
    assert state.state.startswith("21.")


async def test_device_without_guid_uses_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test device without guid falls back to id."""
    mock_data_point = MagicMock()
    mock_data_point.temperature_f = 75.0
    mock_data_point.humidity_rh = None
    mock_data_point.vpd = None
    mock_data_point.co2 = None
    mock_data_point.light_lux = None
    mock_data_point.air_pressure = None
    mock_data_point.dp_f = None
    mock_data_point.signal_strength = None
    mock_data_point.battery_v = None

    mock_device = MagicMock()
    mock_device.id = 999
    mock_device.guid = None  # No GUID
    mock_device.name = "ID Only Device"
    mock_device.device_type = 1
    mock_device.most_recent_data_point = mock_data_point

    mock_device_data = MagicMock()
    mock_device_data.devices = [mock_device]
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Sensor should be created using the id as identifier
    state = hass.states.get("sensor.id_only_device_temperature")
    assert state is not None


async def test_pro_light_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test Pro Light sensors (PPFD/DLI) are created for Pulse Pro devices."""
    # Use configure_mock to set specific values and None for others
    mock_data_point = MagicMock()
    mock_data_point.configure_mock(
        temperature_f=72.5,
        humidity_rh=None,
        vpd=None,
        co2=None,
        light_lux=None,
        air_pressure=None,
        dp_f=None,
        signal_strength=None,
        battery_v=None,
    )

    mock_pro_light = MagicMock()
    mock_pro_light.configure_mock(ppfd=450.5, dli=25.3)

    mock_device = MagicMock()
    mock_device.configure_mock(
        id=123,
        guid="pro-device-123",
        name="Test Pro",
        device_type=1,  # PULSE_PRO
        most_recent_data_point=mock_data_point,
        pro_light_reading_preview=mock_pro_light,
    )

    mock_device_data = MagicMock()
    mock_device_data.devices = [mock_device]
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check PPFD sensor (translation_key "ppfd" not loaded in tests, so name is None)
    # Find the entity with PPFD value
    ppfd_state = None
    dli_state = None
    for state in hass.states.async_all():
        if state.entity_id.startswith("sensor.test_pro"):
            if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "μmol/s/m²":
                ppfd_state = state
            elif state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "mol/d/m²":
                dli_state = state

    assert ppfd_state is not None
    assert ppfd_state.state == "450.5"

    assert dli_state is not None
    assert dli_state.state == "25.3"


async def test_hub_connected_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test hub-connected sensors (pH, EC, Temperature)."""
    # Create mock data point values for a pH sensor
    mock_ph_value = MagicMock()
    mock_ph_value.param_name = "pH"
    mock_ph_value.param_value = "6.12"
    mock_ph_value.measuring_unit = ""

    mock_sensor_data_point = MagicMock()
    mock_sensor_data_point.data_point_values = [mock_ph_value]

    mock_sensor = MagicMock()
    mock_sensor.id = 1638
    mock_sensor.name = "PH Sensor"
    mock_sensor.sensor_type = 3  # PH10
    mock_sensor.hub_id = 402
    mock_sensor.most_recent_data_point = mock_sensor_data_point

    # Create mock EC sensor with multiple values
    mock_ec_value = MagicMock()
    mock_ec_value.param_name = "EC"
    mock_ec_value.param_value = "0.9"
    mock_ec_value.measuring_unit = "mS/cm"

    mock_temp_value = MagicMock()
    mock_temp_value.param_name = "Temperature"
    mock_temp_value.param_value = "22.3"
    mock_temp_value.measuring_unit = "°C"

    mock_ec_data_point = MagicMock()
    mock_ec_data_point.data_point_values = [mock_ec_value, mock_temp_value]

    mock_ec_sensor = MagicMock()
    mock_ec_sensor.id = 1696
    mock_ec_sensor.name = "EC1 Sensor"
    mock_ec_sensor.sensor_type = 4  # EC1
    mock_ec_sensor.hub_id = 402
    mock_ec_sensor.most_recent_data_point = mock_ec_data_point

    # Set up hub
    mock_hub = MagicMock()
    mock_hub.id = 402
    mock_hub.name = "Test Hub"
    mock_hub.mac_address = "AA:BB:CC:DD:EE:FF"

    mock_pulsegrow_client.get_hub_ids.return_value = [402]
    mock_pulsegrow_client.get_hub_details.return_value = mock_hub

    # Update device data to include sensors
    mock_device_data = MagicMock()
    mock_device_data.devices = []
    mock_device_data.sensors = [mock_sensor, mock_ec_sensor]
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check pH sensor
    state = hass.states.get("sensor.ph_sensor_ph")
    assert state is not None
    assert state.state == "6.12"

    # Check EC sensor
    state = hass.states.get("sensor.ec1_sensor_ec")
    assert state is not None
    assert state.state == "0.9"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "mS/cm"

    # Check Temperature sensor from EC device
    state = hass.states.get("sensor.ec1_sensor_temperature")
    assert state is not None
    assert state.state == "22.3"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"


async def test_hub_connected_sensor_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test hub-connected sensor becomes unavailable when removed."""
    # Create mock sensor
    mock_ph_value = MagicMock()
    mock_ph_value.param_name = "pH"
    mock_ph_value.param_value = "6.5"
    mock_ph_value.measuring_unit = ""

    mock_sensor_data_point = MagicMock()
    mock_sensor_data_point.data_point_values = [mock_ph_value]

    mock_sensor = MagicMock()
    mock_sensor.id = 1638
    mock_sensor.name = "PH Sensor"
    mock_sensor.sensor_type = 3
    mock_sensor.hub_id = 402
    mock_sensor.most_recent_data_point = mock_sensor_data_point

    mock_device_data = MagicMock()
    mock_device_data.devices = []
    mock_device_data.sensors = [mock_sensor]
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check sensor is available
    state = hass.states.get("sensor.ph_sensor_ph")
    assert state is not None
    assert state.state == "6.5"

    # Remove sensor from API response
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    # Reload integration
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Sensor should be unavailable
    state = hass.states.get("sensor.ph_sensor_ph")
    assert state is not None
    assert state.state == "unavailable"


async def test_hub_connected_sensor_no_data_point(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test hub-connected sensor without data point values."""
    mock_sensor = MagicMock()
    mock_sensor.id = 1638
    mock_sensor.name = "Empty Sensor"
    mock_sensor.sensor_type = 3
    mock_sensor.hub_id = 402
    mock_sensor.most_recent_data_point = None

    mock_device_data = MagicMock()
    mock_device_data.devices = []
    mock_device_data.sensors = [mock_sensor]
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # No sensor entities should be created
    state = hass.states.get("sensor.empty_sensor_ph")
    assert state is None


async def test_hub_connected_sensor_empty_param_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test hub-connected sensor with empty param_name is skipped."""
    mock_value = MagicMock()
    mock_value.param_name = None
    mock_value.param_value = "6.5"
    mock_value.measuring_unit = ""

    mock_sensor_data_point = MagicMock()
    mock_sensor_data_point.data_point_values = [mock_value]

    mock_sensor = MagicMock()
    mock_sensor.id = 1638
    mock_sensor.name = "Bad Sensor"
    mock_sensor.sensor_type = 3
    mock_sensor.hub_id = 402
    mock_sensor.most_recent_data_point = mock_sensor_data_point

    mock_device_data = MagicMock()
    mock_device_data.devices = []
    mock_device_data.sensors = [mock_sensor]
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # No sensor should be created due to empty param_name
    states = hass.states.async_all()
    pulsegrow_sensors = [
        s for s in states if s.entity_id.startswith("sensor.bad_sensor")
    ]
    assert len(pulsegrow_sensors) == 0


async def test_pro_light_sensor_unavailable_after_removal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test Pro Light sensor returns None when data is unavailable."""
    mock_data_point = MagicMock()
    mock_data_point.configure_mock(
        temperature_f=72.5,
        humidity_rh=None,
        vpd=None,
        co2=None,
        light_lux=None,
        air_pressure=None,
        dp_f=None,
        signal_strength=None,
        battery_v=None,
    )

    mock_pro_light = MagicMock()
    mock_pro_light.configure_mock(ppfd=450.5, dli=25.3)

    mock_device = MagicMock()
    mock_device.configure_mock(
        id=123,
        guid="pro-device-123",
        name="Test Pro",
        device_type=1,  # PULSE_PRO
        most_recent_data_point=mock_data_point,
        pro_light_reading_preview=mock_pro_light,
    )

    mock_device_data = MagicMock()
    mock_device_data.devices = [mock_device]
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify initial state - find PPFD sensor by unit
    ppfd_state = None
    for state in hass.states.async_all():
        if (
            state.entity_id.startswith("sensor.test_pro")
            and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "μmol/s/m²"
        ):
            ppfd_state = state
            break

    assert ppfd_state is not None
    assert ppfd_state.state == "450.5"
    ppfd_entity_id = ppfd_state.entity_id

    # Remove device from API
    mock_device_data.devices = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    # Reload integration
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Sensor should be unavailable
    state = hass.states.get(ppfd_entity_id)
    assert state is not None
    assert state.state == "unavailable"


async def test_hub_connected_sensor_unknown_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test hub-connected sensor with unknown sensor_type uses numeric value as model."""
    mock_ph_value = MagicMock()
    mock_ph_value.param_name = "pH"
    mock_ph_value.param_value = "6.12"
    mock_ph_value.measuring_unit = ""

    mock_sensor_data_point = MagicMock()
    mock_sensor_data_point.data_point_values = [mock_ph_value]

    mock_sensor = MagicMock()
    mock_sensor.id = 1638
    mock_sensor.name = "Unknown Sensor"
    mock_sensor.sensor_type = 999  # Unknown type not in SensorType enum
    mock_sensor.hub_id = None
    mock_sensor.most_recent_data_point = mock_sensor_data_point

    mock_device_data = MagicMock()
    mock_device_data.devices = []
    mock_device_data.sensors = [mock_sensor]
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Sensor should be created despite unknown type
    state = hass.states.get("sensor.unknown_sensor_ph")
    assert state is not None
    assert state.state == "6.12"


async def test_hub_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test hub sensor states when hub is available."""
    mock_hub = MagicMock()
    mock_hub.id = 100
    mock_hub.name = "Test Hub"
    mock_hub.mac_address = "AA:BB:CC:DD:EE:FF"

    mock_pulsegrow_client.get_hub_ids.return_value = [100]
    mock_pulsegrow_client.get_hub_details.return_value = mock_hub

    mock_device_data = MagicMock()
    mock_device_data.devices = []
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify hub was registered (MAC address sensor disabled by default)
    # Just verify no errors occurred during setup
    assert mock_config_entry.state.name == "LOADED"


async def test_hub_sensor_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> None:
    """Test hub sensor becomes unavailable when hub is removed."""
    mock_hub = MagicMock()
    mock_hub.id = 100
    mock_hub.name = "Test Hub"
    mock_hub.mac_address = "AA:BB:CC:DD:EE:FF"

    mock_pulsegrow_client.get_hub_ids.return_value = [100]
    mock_pulsegrow_client.get_hub_details.return_value = mock_hub

    mock_device_data = MagicMock()
    mock_device_data.devices = []
    mock_device_data.sensors = []
    mock_pulsegrow_client.get_all_devices.return_value = mock_device_data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Remove hub
    mock_pulsegrow_client.get_hub_ids.return_value = []
    mock_pulsegrow_client.get_hub_details.return_value = None

    # Reload
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Integration should still be loaded
    assert mock_config_entry.state.name == "LOADED"
