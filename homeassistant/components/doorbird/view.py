"""Support for DoorBird devices."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView

from .const import API_URL, DOMAIN
from .util import get_door_station_by_token


class DoorBirdRequestView(HomeAssistantView):
    """Provide a page for the device to call."""

    requires_auth = False
    url = API_URL
    name = API_URL[1:].replace("/", ":")
    extra_urls = [API_URL + "/{event}"]

    async def get(self, request: web.Request, event: str) -> web.Response:
        """Respond to requests from the device."""
        hass = request.app[KEY_HASS]
        token: str | None = request.query.get("token")
        if (
            token is None
            or (door_station := get_door_station_by_token(hass, token)) is None
        ):
            return web.Response(
                status=HTTPStatus.UNAUTHORIZED, text="Invalid token provided."
            )

        if door_station:
            event_data = door_station.get_event_data(event)
        else:
            event_data = {}

        #
        # This integration uses a multiple different events.
        # It would be a major breaking change to change this to
        # a single event at this point.
        #
        # Do not copy this pattern in the future
        # for any new integrations.
        #
        hass.bus.async_fire(f"{DOMAIN}_{event}", event_data)
        return web.Response(text="OK")
