"""Tests for the HAVEN IAQ integration."""

from ipaddress import ip_address

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

TEST_HOST = "192.0.2.1"
TEST_PORT = 80
TEST_PATH = "/api/v1"
TEST_SERIAL = "TEST-RAM-0001"
TEST_CAM_SERIAL = "TEST-CAM-0001"

TEST_INFO = {
    "api_version": 1,
    "serial_number": TEST_SERIAL,
    "device_id": "TEST-DEVICE-RAM",
    "manufacturer": "HAVEN IAQ",
    "model": "Room Air Monitor",
    "product_type": "ram",
    "fw_ver": "test-firmware",
    "hw_version": "test-hardware",
    "capabilities": ["air_quality"],
}

TEST_CAM_INFO = {
    **TEST_INFO,
    "serial_number": TEST_CAM_SERIAL,
    "device_id": "TEST-DEVICE-CAM",
    "model": "Central Air Monitor",
    "product_type": "cam",
    "capabilities": ["air_quality", "airflow"],
}

TEST_UNSUPPORTED_CONTROLLER_INFO = {
    **TEST_INFO,
    "serial_number": "TEST-CAC-0001",
    "device_id": "TEST-DEVICE-CAC",
    "model": "HAVEN Controller",
    "product_type": "cac",
    "capabilities": ["relay_state"],
}

TEST_SENSORS = {
    "sensor_ready": True,
    "temperature_c": 22.5,
    "humidity_pct": 45.0,
    "dew_point_c": 10.0,
    "co2_ppm": 500,
    "tvoc_index": 100,
    "nox_index": 1,
    "pm1_ugm3": 0.1,
    "pm25_ugm3": 1.0,
    "pm4_ugm3": 1.0,
    "pm10_ugm3": 1.0,
    "pm05_count_cm3": 0.7,
    "pm1_count_cm3": 0.9,
    "pm25_count_cm3": 0.9,
    "pm4_count_cm3": 0.9,
    "pm10_count_cm3": 0.9,
}

TEST_CAM_SENSORS = {
    "sensor_ready": True,
    "latest_sensor_age_s": 2,
    "temperature_c": 22.5,
    "humidity_pct": 45.0,
    "pressure_kpa": 101.3,
    "co2_ppm": 500,
    "tvoc_ppb": 75.0,
    "pm25_ugm3": 1.0,
    "pm10_ugm3": 1.0,
    "pm25_count_cm3": 0.9,
    "pm10_count_cm3": 0.9,
    "airflow_mps": 1.25,
    "airflow_duration_s": 30.0,
}

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
