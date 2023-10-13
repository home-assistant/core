"""Mock inputs for tests."""
from homeassistant.components.acaia.const import (
    CONF_IS_NEW_STYLE_SCALE,
    CONF_MAC_ADDRESS,
    CONF_NAME,
)
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

USER_INPUT = {
    CONF_MAC_ADDRESS: "11:22:33:44:55",
    CONF_NAME: "MyScale",
    CONF_IS_NEW_STYLE_SCALE: True,
}

SERVICE_INFO = BluetoothServiceInfo(
    name="LUNAR_1234",
    address="11:22:33:44:55",
    rssi=-63,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
)
