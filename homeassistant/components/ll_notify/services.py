"""ll_notify public services."""

from functools import partial

from .const import DOMAIN
from .ws_out import ws_send_message

DEFAULT_MESSAGE = "DEFAULT MESSAGE - You are probably not calling this properly!"


async def setup_services(hass, config):
    """Register all ll_notify services."""

    #
    # success, error, warning, message, notify, dismiss_all
    #
    async def handle_generic_ws_call(event_type, call):
        """Handle certain websocket calls.

        Just pass through the websocket data back to the websocket.
        This allows you to have a button or action that does "ll_notify/success" in the UI
        and have that trigger the front end to run a success notification.
        """
        ws_send_message(hass, event_type=event_type, event_data=call.data)
        return True

    ws_events = [
        "success",
        "error",
        "warning",
        "message",
        "notify",
        "alert",
        "confirm",
        "dismiss_all",
    ]
    for event_type in ws_events:
        handler = partial(handle_generic_ws_call, event_type)
        hass.services.async_register(DOMAIN, event_type, handler)

    #
    # get_defaults
    #
    async def handle_get_defaults(call):
        """Handle ll_notify/get_defaults."""
        defaults = config.get(DOMAIN, {}).get("defaults")
        ws_send_message(hass, event_type="get_defaults", event_data=defaults)
        return True

    hass.services.async_register(DOMAIN, "get_defaults", handle_get_defaults)

    #
    # ping
    #
    async def handle_ping(call):
        """Handle ll_notify/ping."""
        ws_send_message(hass, event_type="ping", event_data=call.data)
        return True

    hass.services.async_register(DOMAIN, "ping", handle_ping)

    #
    # fire_event
    #
    async def handle_fire_event(call):
        """Handle ll_notify/fire_event."""

        if "event_name" not in call.data:
            return
        hass.bus.async_fire(call.data["event_name"], call.data.get("event_data"))
        return True

    hass.services.async_register(DOMAIN, "fire_event", handle_fire_event)

    return True
