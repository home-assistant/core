"""Tests for the SwitchBot Cloud integration."""

from switchbot_api import Device

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        CONF_API_TOKEN: "test-token",
        CONF_API_KEY: "test-api-key",
    }
    entry = MockConfigEntry(
        domain=DOMAIN, data=config, entry_id="123456", unique_id="123456"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


AIR_PURIFIER_INFO = Device(
    version="V1.0",
    deviceId="air-purifier-id-1",
    deviceName="air-purifier-1",
    deviceType="Air Purifier Table PM2.5",
    hubDeviceId="test-hub-id",
)

CIRCULATOR_FAN_INFO = Device(
    version="V1.0",
    deviceId="battery-fan-id-1",
    deviceName="battery-fan-1",
    deviceType="Battery Circulator Fan",
    hubDeviceId="test-hub-id",
)


METER_INFO = Device(
    version="V1.0",
    deviceId="meter-id-1",
    deviceName="meter-1",
    deviceType="Meter",
    hubDeviceId="test-hub-id",
)

CONTACT_SENSOR_INFO = Device(
    version="V1.7",
    deviceId="contact-sensor-id",
    deviceName="contact-sensor-name",
    deviceType="Contact Sensor",
    hubDeviceId="test-hub-id",
)

HUB3_INFO = Device(
    version="V1.3-0.8-0.1",
    deviceId="hub3-id",
    deviceName="Hub-3-name",
    deviceType="Hub 3",
    hubDeviceId="test-hub-id",
)

MOTION_SENSOR_INFO = Device(
    version="V1.9",
    deviceId="motion-sensor-id",
    deviceName="motion-sensor-name",
    deviceType="Motion Sensor",
    hubDeviceId="test-hub-id",
)

WATER_DETECTOR_INFO = Device(
    version="V1.7",
    deviceId="water-detector-id",
    deviceName="water-detector-name",
    deviceType="Water Detector",
    hubDeviceId="test-hub-id",
)
