"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.device_tracker import (
    ATTR_ATTRIBUTES,
    ATTR_BATTERY,
    ATTR_DEV_ID,
    ATTR_GPS,
    ATTR_GPS_ACCURACY,
    ATTR_HOST_NAME,
    ATTR_LOCATION_NAME,
    ATTR_MAC,
    DOMAIN,
    SERVICE_SEE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import GPSType
from homeassistant.loader import bind_hass


@callback
@bind_hass
def async_see(
    hass: HomeAssistant,
    mac: str = None,
    dev_id: str = None,
    host_name: str = None,
    location_name: str = None,
    gps: GPSType = None,
    gps_accuracy=None,
    battery: int = None,
    attributes: dict = None,
):
    """Call service to notify you see device."""
    data = {
        key: value
        for key, value in (
            (ATTR_MAC, mac),
            (ATTR_DEV_ID, dev_id),
            (ATTR_HOST_NAME, host_name),
            (ATTR_LOCATION_NAME, location_name),
            (ATTR_GPS, gps),
            (ATTR_GPS_ACCURACY, gps_accuracy),
            (ATTR_BATTERY, battery),
        )
        if value is not None
    }
    if attributes:
        data[ATTR_ATTRIBUTES] = attributes
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_SEE, data))
