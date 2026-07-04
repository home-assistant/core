"""Constants used for mocking data."""

from ipaddress import ip_address

from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.0.1"),
    ip_addresses=[ip_address("192.168.0.1")],
    port=14791,
    hostname="test.local.",
    type="_dvl-deviceapi._tcp.local.",
    name="dvl-deviceapi",
    properties={
        "Path": "/deviceapi",
        "Version": "v0",
        "Features": "",
        "MT": "2600",
        "SN": "1234567890",
        "FirmwareVersion": "8.90.4",
        "PlcMacAddress": "AA:BB:CC:DD:EE:FF",
    },
)

DISCOVERY_INFO_WRONG_DEVOLO_DEVICE = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.0.1"),
    ip_addresses=[ip_address("192.168.0.1")],
    hostname="mock_hostname",
    name="mock_name",
    port=None,
    properties={"MT": "2700"},
    type="mock_type",
)

DISCOVERY_INFO_WRONG_DEVICE = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.0.1"),
    ip_addresses=[ip_address("192.168.0.1")],
    hostname="mock_hostname",
    name="mock_name",
    port=None,
    properties={"Features": ""},
    type="mock_type",
)
