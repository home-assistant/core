"""Test the SensorPush config flow."""

from unittest.mock import patch

from sensorpush_ble import (
    DeviceClass,
    DeviceKey,
    SensorDescription,
    SensorDeviceInfo,
    SensorUpdate,
    SensorValue,
    Units,
)

from homeassistant import config_entries
from homeassistant.components.sensorpush.const import DOMAIN
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

NOT_SENSOR_PUSH_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

HTW_SERVICE_INFO = BluetoothServiceInfo(
    name="SensorPush HT.w 0CA1",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={11271: b"\xfe\x00\x01"},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)
HTW_SENSOR_UPDATE = SensorUpdate(
    title=None,
    devices={
        None: SensorDeviceInfo(
            model="HTP.w",
            manufacturer="SensorPush",
            name="HTP.w 0CA1",
            sw_version=None,
            hw_version=None,
        )
    },
    entity_descriptions={
        DeviceKey(key="temperature", device_id=None): SensorDescription(
            device_key=DeviceKey(key="temperature", device_id=None),
            device_class=DeviceClass.TEMPERATURE,
            native_unit_of_measurement=Units.TEMP_CELSIUS,
        ),
        DeviceKey(key="humidity", device_id=None): SensorDescription(
            device_key=DeviceKey(key="humidity", device_id=None),
            device_class=DeviceClass.HUMIDITY,
            native_unit_of_measurement=Units.PERCENTAGE,
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorDescription(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            device_class=DeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement=Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        ),
    },
    entity_values={
        DeviceKey(key="temperature", device_id=None): SensorValue(
            device_key=DeviceKey(key="temperature", device_id=None),
            native_value=20.21,
            name="Temperature",
        ),
        DeviceKey(key="humidity", device_id=None): SensorValue(
            device_key=DeviceKey(key="humidity", device_id=None),
            native_value=45.08,
            name="Humidity",
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorValue(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            name="Signal Strength",
            native_value=-60,
        ),
    },
)
HTPWX_SERVICE_INFO = BluetoothServiceInfo(
    name="SensorPush HTP.xw F4D",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={7168: b"\xcd=!\xd1\xb9"},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)
HTPWX_SENSOR_UPDATE = SensorUpdate(
    title=None,
    devices={
        None: SensorDeviceInfo(
            model="HTP.xw",
            manufacturer="SensorPush",
            name="HTP.xw F4D",
            sw_version=None,
            hw_version=None,
        )
    },
    entity_descriptions={
        DeviceKey(key="temperature", device_id=None): SensorDescription(
            device_key=DeviceKey(key="temperature", device_id=None),
            device_class=DeviceClass.TEMPERATURE,
            native_unit_of_measurement=Units.TEMP_CELSIUS,
        ),
        DeviceKey(key="humidity", device_id=None): SensorDescription(
            device_key=DeviceKey(key="humidity", device_id=None),
            device_class=DeviceClass.HUMIDITY,
            native_unit_of_measurement=Units.PERCENTAGE,
        ),
        DeviceKey(key="pressure", device_id=None): SensorDescription(
            device_key=DeviceKey(key="pressure", device_id=None),
            device_class=DeviceClass.PRESSURE,
            native_unit_of_measurement=Units.PRESSURE_MBAR,
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorDescription(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            device_class=DeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement=Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        ),
    },
    entity_values={
        DeviceKey(key="temperature", device_id=None): SensorValue(
            device_key=DeviceKey(key="temperature", device_id=None),
            native_value=20.34,
            name="Temperature",
        ),
        DeviceKey(key="humidity", device_id=None): SensorValue(
            device_key=DeviceKey(key="humidity", device_id=None),
            native_value=46.27,
            name="Humidity",
        ),
        DeviceKey(key="pressure", device_id=None): SensorValue(
            device_key=DeviceKey(key="pressure", device_id=None),
            native_value=1009.21,
            name="Pressure",
        ),
        DeviceKey(key="signal_strength", device_id=None): SensorValue(
            device_key=DeviceKey(key="signal_strength", device_id=None),
            native_value=-55,
            name="Signal Strength",
        ),
    },
)


async def test_async_step_bluetooth_valid_device(hass):
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HTPWX_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "HTP.xw F4D"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "4125DDBA-2774-4851-9889-6AADDD4CAC3D"


async def test_async_step_bluetooth_not_sensorpush(hass):
    """Test discovery via bluetooth not sensorpush."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_SENSOR_PUSH_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_user_no_devices_found(hass):
    """Test setup from service info cache with no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_with_found_devices(hass):
    """Test setup from service info cache with devices found."""
    with patch(
        "homeassistant.components.sensorpush.config_flow.async_discovered_service_info",
        return_value=[HTW_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "61DE521B-F0BF-9F44-64D4-75BBE1738105"},
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "HT.w 0CA1"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "61DE521B-F0BF-9F44-64D4-75BBE1738105"


async def test_async_step_user_with_found_devices_already_setup(hass):
    """Test setup from service info cache with devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensorpush.config_flow.async_discovered_service_info",
        return_value=[HTW_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
