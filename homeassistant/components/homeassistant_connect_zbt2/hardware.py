"""The Home Assistant Connect ZBT-2 hardware platform."""

from __future__ import annotations

from homeassistant.components.hardware.models import HardwareInfo, USBInfo
from homeassistant.core import HomeAssistant, callback

from .config_flow import HomeAssistantConnectZBT2ConfigFlow
from .const import DOMAIN, HARDWARE_NAME, MANUFACTURER, PID, PRODUCT, SERIAL_NUMBER, VID

DOCUMENTATION_URL = (
    "https://support.nabucasa.com/hc/en-us/categories/"
    "24734620813469-Home-Assistant-Connect-ZBT-1"
)
EXPECTED_ENTRY_VERSION = (
    HomeAssistantConnectZBT2ConfigFlow.VERSION,
    HomeAssistantConnectZBT2ConfigFlow.MINOR_VERSION,
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
            name=HARDWARE_NAME,
            url=DOCUMENTATION_URL,
        )
        for entry in entries
        # Ignore unmigrated config entries in the hardware page
        if (entry.version, entry.minor_version) == EXPECTED_ENTRY_VERSION
    ]
