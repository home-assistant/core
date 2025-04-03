"""The Home Assistant SkyConnect hardware platform."""

from __future__ import annotations

from homeassistant.components.hardware.models import HardwareInfo, USBInfo
from homeassistant.core import HomeAssistant, callback

from .config_flow import HomeAssistantSkyConnectConfigFlow
from .const import DOMAIN, MANUFACTURER, PID, PRODUCT, SERIAL_NUMBER, VID
from .util import get_hardware_variant

DOCUMENTATION_URL = "https://skyconnect.home-assistant.io/documentation/"
EXPECTED_ENTRY_VERSION = (
    HomeAssistantSkyConnectConfigFlow.VERSION,
    HomeAssistantSkyConnectConfigFlow.MINOR_VERSION,
)


@callback
def async_info(hass: HomeAssistant) -> list[HardwareInfo]:
    """Return board info."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return [
        HardwareInfo(
            board=None,
            config_entries=[entry.entry_id],
            dongle=USBInfo(
                vid=entry.data[VID],
                pid=entry.data[PID],
                serial_number=entry.data[SERIAL_NUMBER],
                manufacturer=entry.data[MANUFACTURER],
                description=entry.data[PRODUCT],
            ),
            name=get_hardware_variant(entry).full_name,
            url=DOCUMENTATION_URL,
        )
        for entry in entries
        # Ignore unmigrated config entries in the hardware page
        if (entry.version, entry.minor_version) < EXPECTED_ENTRY_VERSION
    ]
