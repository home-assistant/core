"""Constants used in shark iq tests."""

from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME

# Dummy device dict of the form returned by AylaApi.list_devices()
SHARK_DEVICE_DICT = {
    "product_name": "Sharknado",
    "model": "AY001MRT1",
    "dsn": "AC000Wxxxxxxxxx",
    "oem_model": "RV1000A",
    "sw_version": "devd 1.7 2020-05-13 11:50:36",
    "template_id": 99999,
    "mac": "ffffffffffff",
    "unique_hardware_id": None,
    "lan_ip": "192.168.0.123",
    "connected_at": "2020-07-31T08:03:05Z",
    "key": 26517570,
    "lan_enabled": False,
    "has_properties": True,
    "product_class": None,
    "connection_status": "Online",
    "lat": "99.9999",
    "lng": "-99.9999",
    "locality": "99999",
    "device_type": "Wifi",
}

# Dummy response for get_metadata
SHARK_METADATA_DICT = [
    {
        "datum": {
            "created_at": "2019-12-02T02:13:12Z",
            "from_template": False,
            "key": "sharkDeviceMobileData",
            "updated_at": "2019-12-02T02:13:12Z",
            "value": '{"vacModelNumber":"RV1001AE","vacSerialNumber":"S26xxxxxxxxx"}',
            "dsn": "AC000Wxxxxxxxxx",
        }
    }
]

# Dummy shark.properties_full for testing.  NB: this only includes those properties in the tests
SHARK_PROPERTIES_DICT = {
    "Battery_Capacity": {"base_type": "integer", "read_only": True, "value": 50},
    "Charging_Status": {"base_type": "boolean", "read_only": True, "value": 0},
    "CleanComplete": {"base_type": "boolean", "read_only": True, "value": 0},
    "Cleaning_Statistics": {"base_type": "file", "read_only": True, "value": None},
    "DockedStatus": {"base_type": "boolean", "read_only": True, "value": 0},
    "Error_Code": {"base_type": "integer", "read_only": True, "value": 7},
    "Evacuating": {"base_type": "boolean", "read_only": True, "value": 1},
    "Find_Device": {"base_type": "boolean", "read_only": False, "value": 0},
    "LowLightMission": {"base_type": "boolean", "read_only": True, "value": 0},
    "Nav_Module_FW_Version": {
        "base_type": "string",
        "read_only": True,
        "value": "V3.4.11-20191015",
    },
    "Operating_Mode": {"base_type": "integer", "read_only": False, "value": 2},
    "Power_Mode": {"base_type": "integer", "read_only": False, "value": 1},
    "RSSI": {"base_type": "integer", "read_only": True, "value": -46},
    "Recharge_Resume": {"base_type": "boolean", "read_only": False, "value": 1},
    "Recharging_To_Resume": {"base_type": "boolean", "read_only": True, "value": 0},
    "Robot_Firmware_Version": {
        "base_type": "string",
        "read_only": True,
        "value": "Dummy Firmware 1.0",
    },
    "Robot_Room_List": {
        "base_type": "string",
        "read_only": True,
        "value": "Kitchen",
    },
}

TEST_USERNAME = "test-username"
TEST_PASSWORD = "test-password"
TEST_REGION = "elsewhere"
UNIQUE_ID = "foo@bar.com"
CONFIG = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_REGION: TEST_REGION,
}
CONFIG_NO_REGION = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
}
ENTRY_ID = "0123456789abcdef0123456789abcdef"
