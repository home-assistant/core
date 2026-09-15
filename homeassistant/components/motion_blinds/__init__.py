"""The motion_blinds component."""

import asyncio
from dataclasses import dataclass, field
import logging

from motionblinds import DEVICE_TYPES_GATEWAY, DEVICE_TYPES_WIFI, AsyncMotionMulticast

from homeassistant.const import CONF_API_KEY, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_BLIND_TYPE_LIST,
    CONF_INTERFACE,
    DEFAULT_INTERFACE,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import DataUpdateCoordinatorMotionBlinds, MotionBlindsConfigEntry
from .entity import gateway_device_info
from .gateway import ConnectMotionGateway

_LOGGER = logging.getLogger(__name__)


@dataclass
class MotionBlindsData:
    """Multicast listener shared by every gateway."""

    setup_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    multicast: AsyncMotionMulticast | None = None
    unsub_stop: CALLBACK_TYPE | None = None


# One multicast listener serves every gateway, so it is shared between config
# entries rather than owned by any one of them.
MOTION_BLINDS_DATA: HassKey[MotionBlindsData] = HassKey(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant, entry: MotionBlindsConfigEntry
) -> bool:
    """Set up the motion_blinds components from a config entry."""
    if (motion_data := hass.data.get(MOTION_BLINDS_DATA)) is None:
        motion_data = hass.data[MOTION_BLINDS_DATA] = MotionBlindsData()
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_API_KEY]
    multicast_interface = entry.data.get(CONF_INTERFACE, DEFAULT_INTERFACE)
    blind_type_list = entry.data.get(CONF_BLIND_TYPE_LIST)

    # Create multicast Listener
    async with motion_data.setup_lock:
        if (multicast := motion_data.multicast) is None:
            # check multicast interface
            check_multicast_class = ConnectMotionGateway(
                hass, interface=multicast_interface
            )
            working_interface = await check_multicast_class.async_check_interface(
                host, key
            )
            if working_interface != multicast_interface:
                data = {**entry.data, CONF_INTERFACE: working_interface}
                hass.config_entries.async_update_entry(entry, data=data)
                _LOGGER.debug(
                    (
                        "Motionblinds interface updated from %s to %s, "
                        "this should only occur after a network change"
                    ),
                    multicast_interface,
                    working_interface,
                )

            multicast = motion_data.multicast = AsyncMotionMulticast(
                interface=working_interface
            )
            # start listening for local pushes (only once)
            await multicast.Start_listen()

            # register stop callback to shutdown listening for local pushes
            def stop_motion_multicast(event):
                """Stop multicast thread."""
                _LOGGER.debug("Shutting down Motion Listener")
                multicast.Stop_listen()

            motion_data.unsub_stop = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, stop_motion_multicast
            )

    # Connect to motion gateway
    connect_gateway_class = ConnectMotionGateway(hass, multicast)
    if not await connect_gateway_class.async_connect_gateway(
        host, key, blind_type_list
    ):
        raise ConfigEntryNotReady
    motion_gateway = connect_gateway_class.gateway_device

    coordinator = DataUpdateCoordinatorMotionBlinds(
        hass, entry, _LOGGER, motion_gateway
    )

    # store blind type list for next time
    if entry.data.get(CONF_BLIND_TYPE_LIST) != motion_gateway.blind_type_list:
        data = {
            **entry.data,
            CONF_BLIND_TYPE_LIST: motion_gateway.blind_type_list,
        }
        hass.config_entries.async_update_entry(entry, data=data)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Register the gateway device up front so child blinds can resolve it as their
    # via_device parent regardless of the order platforms are set up in. The any()
    # is the exact complement of the children's linking condition, so the gateway is
    # still registered if it self-reports an unexpected device_type while RF (non
    # Wi-Fi) blinds depend on it.
    if motion_gateway.device_type in DEVICE_TYPES_GATEWAY or any(
        blind.device_type not in DEVICE_TYPES_WIFI
        for blind in motion_gateway.device_list.values()
    ):
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            **gateway_device_info(motion_gateway),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MotionBlindsConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    motion_data = hass.data[MOTION_BLINDS_DATA]
    if unload_ok and motion_data.multicast is not None:
        motion_data.multicast.Unregister_motion_gateway(config_entry.data[CONF_HOST])

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        # No motion gateways left, stop Motion multicast
        if motion_data.unsub_stop is not None:
            motion_data.unsub_stop()
            motion_data.unsub_stop = None
        _LOGGER.debug("Shutting down Motion Listener")
        if motion_data.multicast is not None:
            motion_data.multicast.Stop_listen()
            motion_data.multicast = None

    return unload_ok
