"""Support for tracking a Volvo."""
from __future__ import annotations

from homeassistant.components.device_tracker import AsyncSeeCallback, SourceType
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import DATA_KEY, SIGNAL_STATE_UPDATED, VolvoUpdateCoordinator


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the Volvo tracker."""
    if discovery_info is None:
        return False

    vin, component, attr, slug_attr = discovery_info
    coordinator: VolvoUpdateCoordinator = hass.data[DATA_KEY]
    volvo_data = coordinator.volvo_data
    instrument = volvo_data.instrument(vin, component, attr, slug_attr)

    if instrument is None:
        return False

    async def see_vehicle() -> None:
        """Handle the reporting of the vehicle position."""
        host_name = instrument.vehicle_name
        dev_id = f"volvo_{slugify(host_name)}"
        await async_see(
            dev_id=dev_id,
            host_name=host_name,
            source_type=SourceType.GPS,
            gps=instrument.state,
            icon="mdi:car",
        )

    async_dispatcher_connect(hass, SIGNAL_STATE_UPDATED, see_vehicle)

    return True
