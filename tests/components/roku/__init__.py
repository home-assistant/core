"""Tests for the Roku component."""
from homeassistant.components.roku.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

HOST = "1.2.3.4"
NAME = "Roku 3"
SSDP_LOCATION = "http://1.2.3.4/"
UPNP_FRIENDLY_NAME = "My Roku 3"
UPNP_SERIAL = "1GU48T017973"


class MockDeviceInfo(object):
    """Mock DeviceInfo for Roku."""

    model_name = NAME
    model_num = "4200X"
    software_version = "7.5.0.09021"
    serial_num = UPNP_SERIAL
    user_device_name = UPNP_FRIENDLY_NAME
    roku_type = "Box"

    def __repr__(self):
        """Return the object representation of DeviceInfo."""
        return "<DeviceInfo: %s-%s, SW v%s, Ser# %s (%s)>" % (
            self.model_name,
            self.model_num,
            self.software_version,
            self.serial_num,
            self.roku_type,
        )


async def setup_integration(
    hass: HomeAssistantType, skip_entry_setup: bool = False
) -> MockConfigEntry:
    """Set up the Roku integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=UPNP_SERIAL, data={CONF_HOST: HOST}
    )

    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
