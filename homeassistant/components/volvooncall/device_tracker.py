"""Support for tracking a Volvo."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import DATA_KEY, SIGNAL_STATE_UPDATED


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: Callable[..., Awaitable[None]],
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the Volvo tracker."""
    if discovery_info is None:
        return False

    vin, component, attr, slug_attr = discovery_info
    data = hass.data[DATA_KEY]
    instrument = data.instrument(vin, component, attr, slug_attr)

    async def see_vehicle():
        """Handle the reporting of the vehicle position."""
        host_name = instrument.vehicle_name
        dev_id = f"volvo_{slugify(host_name)}"
        await async_see(
            dev_id=dev_id,
            host_name=host_name,
            source_type=SOURCE_TYPE_GPS,
            gps=instrument.state,
            icon="mdi:car",
        )

    async_dispatcher_connect(hass, SIGNAL_STATE_UPDATED, see_vehicle)

    return True
