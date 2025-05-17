"""Common methods used across tests for air-Q."""

from aioairq import DeviceInfo

from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD

TEST_USER_DATA = {
    CONF_IP_ADDRESS: "192.168.0.0",
    CONF_PASSWORD: "password",
}
TEST_DEVICE_INFO = DeviceInfo(
    id="id",
    name="airq_name",
    model="model",
    sw_version="sw",
    hw_version="hw",
)
TEST_DEVICE_DATA = {"co2": 500.0, "Status": "OK", "brightness": 5}
