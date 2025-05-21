"""Common methods used across tests for air-Q."""

from aioairq import DeviceInfo

from homeassistant.components.airq.const import DOMAIN
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
TEST_DEVICE_DATA = {"co2": 500.0, "Status": "OK"}
TEST_BRIGHTNESS = 42


async def setup_platform(hass: HomeAssistant) -> None:
    """Load AirQ integration.

    This function does not patch AirQ itself, rather it depends on being
    run in presence of `mock_coordinator_airq` fixture, which patches calls
    by `AirQCoordinator.airq`, which are done under `async_setup`.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_USER_DATA, unique_id=TEST_DEVICE_INFO["id"]
    )
    config_entry.add_to_hass(hass)

    # The patching is now handled by the mock_coorinator_airq fixture.
    # We just need to load the component.
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
