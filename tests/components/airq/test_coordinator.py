"""Test the air-Q data update coordinator."""
from unittest.mock import patch

from aioairq.core import DeviceInfo

from homeassistant.components.airq.const import DOMAIN, MANUFACTURER
from homeassistant.components.airq.coordinator import AirQCoordinator
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_USER_DATA = {
    CONF_IP_ADDRESS: "192.168.0.0",
    CONF_PASSWORD: "password",
}
TEST_DEVICE_INFO = DeviceInfo(
    id="id",
    name="name",
    model="model",
    sw_version="sw",
    hw_version="hw",
)
DEVICE_INFO_INIT = {
    "manufacturer": MANUFACTURER,
    "identifiers": {(DOMAIN, TEST_DEVICE_INFO["id"])},
}
DEVICE_INFO_UPDETED = DEVICE_INFO_INIT | {
    k: TEST_DEVICE_INFO[k] for k in ["name", "model", "sw_version", "hw_version"]
}


async def test_fetch_device_info_on_first_update(hass: HomeAssistant) -> None:
    """Test that device_info is updated after the first _async_update_data."""
    entry = MockConfigEntry(
        data=TEST_USER_DATA,
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO["id"],
    )

    coordinator = AirQCoordinator(hass, entry)
    assert coordinator.device_info == DEVICE_INFO_INIT
    with patch("aioairq.AirQ.get", return_value={}), patch(
        "aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO
    ):
        await coordinator._async_update_data()
    assert coordinator.device_info == DEVICE_INFO_UPDETED
