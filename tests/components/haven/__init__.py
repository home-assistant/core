"""Tests for the HAVEN IAQ integration."""

from ipaddress import ip_address

from homeassistant.components.haven.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_HOST = "192.0.2.1"
TEST_PORT = 80
TEST_PATH = "/api/v1"
TEST_SERIAL = "TEST-RAM-0001"
TEST_CAM_SERIAL = "TEST-CAM-0001"

TEST_INFO = load_json_object_fixture("ram_info.json", DOMAIN)
TEST_CAM_INFO = load_json_object_fixture("cam_info.json", DOMAIN)
TEST_UNSUPPORTED_CONTROLLER_INFO = load_json_object_fixture(
    "controller_info.json", DOMAIN
)
TEST_SENSORS = load_json_object_fixture("ram_sensors.json", DOMAIN)
TEST_CAM_SENSORS = load_json_object_fixture("cam_sensors.json", DOMAIN)

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(TEST_HOST),
    ip_addresses=[ip_address(TEST_HOST)],
    hostname="haven-test-device.local.",
    name="HAVEN test device._haven._tcp.local.",
    port=TEST_PORT,
    properties={
        "serial": TEST_SERIAL,
        "model": "Room Air Monitor",
        "product": "ram",
        "fw": "test-firmware",
        "path": TEST_PATH,
    },
    type="_haven._tcp.local.",
)


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the HAVEN integration for tests."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
