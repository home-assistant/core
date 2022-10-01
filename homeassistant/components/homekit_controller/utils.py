"""Helper functions for the homekit_controller component."""
from typing import cast

from aiohomekit import Controller

from homeassistant.components import bluetooth, zeroconf
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant

from .const import CONTROLLER
from .storage import async_get_entity_storage


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
