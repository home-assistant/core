"""Tests for the Airthings integration."""

from airthings import Airthings, AirthingsDevice

from homeassistant.core import HomeAssistant

from .const import TEST_DATA

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Airthings integration in Home Assistant."""
    entry = MockConfigEntry(
        domain="airthings",
        data=TEST_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


class MockAirthings(Airthings):
    """Mock Airthings class to simulate device data."""

    def __init__(self, devices) -> None:
        """Initialize with a dictionary of devices."""
        super().__init__(client_id="", secret="", websession=None)
        self.devices = devices

    async def update_devices(self) -> dict[str, AirthingsDevice]:
        """Mock method to return devices."""
        return self.devices
