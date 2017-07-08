import asyncio
import logging
import xknx

from homeassistant.components.xknx import _LOGGER, DATA_XKNX, \
    XKNXSwitch

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices_callback, \
        discovery_info=None):
    """Setup the XKNX switch platform."""
    if DATA_XKNX not in hass.data \
            or not hass.data[DATA_XKNX].initialized:
        return False

    entities = []

    for device in hass.data[DATA_XKNX].xknx.devices:
        if isinstance(device, xknx.Outlet):
            entities.append(XKNXSwitch(hass, device))

    async_add_devices_callback(entities)

    return True
