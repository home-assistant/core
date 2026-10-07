"""Tests for the Qube Heat Pump integration."""

from python_qube_heatpump import QubeDeviceInfo

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Qube Heat Pump integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


DEVICE_INFO = QubeDeviceInfo(
    uuid="000100000007B5EA",
    software_version="4.1.00",
    controller_firmware="v5.1.007",
    project_name="DEQSIHPB000CR",
)
