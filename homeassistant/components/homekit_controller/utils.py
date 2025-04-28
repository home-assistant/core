"""Helper functions for the homekit_controller component."""

from functools import lru_cache
from typing import cast

from aiohomekit import Controller

from homeassistant.components import bluetooth, zeroconf
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant

from .const import CONTROLLER
from .storage import async_get_entity_storage

type IidTuple = tuple[int, int | None, int | None]


def unique_id_to_iids(unique_id: str) -> IidTuple | None:
    """Convert a unique_id to a tuple of accessory id, service iid and characteristic iid.

    Depending on the field in the accessory map that is referenced, some of these may be None.

    Returns None if this unique_id doesn't follow the homekit_controller scheme and is invalid.
    """
    try:
        match unique_id.split("_"):
            case (unique_id, aid, sid, cid):
                return (int(aid), int(sid), int(cid))
            case (unique_id, aid, sid):
                return (int(aid), int(sid), None)
            case (unique_id, aid):
                return (int(aid), None, None)
    except ValueError:
        # One of the int conversions failed - this can't be a valid homekit_controller unique id
        # Fall through and return None
        pass

    return None


@lru_cache
def folded_name(name: str) -> str:
    """Return a name that is used for matching a similar string."""
    return name.casefold().replace(" ", "")


async def async_get_controller(hass: HomeAssistant) -> Controller:
    """Get or create an aiohomekit Controller instance."""
    if existing := hass.data.get(CONTROLLER):
        return cast(Controller, existing)

    async_zeroconf_instance = await zeroconf.async_get_async_instance(hass)

    char_cache = await async_get_entity_storage(hass)

    # In theory another call to async_get_controller could have run while we were
    # trying to get the zeroconf instance. So we check again to make sure we
    # don't leak a Controller instance here.
    if existing := hass.data.get(CONTROLLER):
        return cast(Controller, existing)

    bleak_scanner_instance = bluetooth.async_get_scanner(hass)

    controller = Controller(
        async_zeroconf_instance=async_zeroconf_instance,
        bleak_scanner_instance=bleak_scanner_instance,  # type: ignore[arg-type]
        char_cache=char_cache,
    )

    hass.data[CONTROLLER] = controller

    async def _async_stop_homekit_controller(event: Event) -> None:
        # Pop first so that in theory another controller /could/ start
        # While this one was shutting down
        hass.data.pop(CONTROLLER, None)
        await controller.async_stop()

    # Right now _async_stop_homekit_controller is only called on HA exiting
    # So we don't have to worry about leaking a callback here.
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_homekit_controller)

    await controller.async_start()

    return controller
