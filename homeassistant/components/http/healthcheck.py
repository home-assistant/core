"""Healthcheck logic for HTTP component."""
from __future__ import annotations

import logging
from aiohttp.web import json_response
from datetime import timedelta

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

_LOGGER: Final = logging.getLogger(__name__)

KEY_HEALTHCHECK_THRESHOLD = "ha_healthcheck_threshold"
KEY_HEALTHCHECK_LAST_SUCCESS = "ha_healthcheck_last_success"

HEALTHCHECK_ENDPOINT = "/healthcheck"
HEALTHCHECK_EVENT = "healthcheck_event"
HEALTHCHECK_INTERVAL = 10


def setup_healthcheck(
    hass: HomeAssistant, app: Application, healthcheck_threshold: int
) -> None:
    app[KEY_HEALTHCHECK_THRESHOLD] = healthcheck_threshold
    app[KEY_HEALTHCHECK_LAST_SUCCESS] = dt_util.utcnow()

    app.router.add_route("GET", HEALTHCHECK_ENDPOINT, handle_healthcheck_request)

    async def fire_healthcheck_event(now):
        event_data = {
            "now": now,
        }
        _LOGGER.debug(f"Firing healthcheck event")
        hass.bus.async_fire(HEALTHCHECK_EVENT, event_data)

    async def handle_healthcheck_event(event):
        if event.data.get("now") is not None:
            _LOGGER.debug(f"Received healthcheck event")
            app[KEY_HEALTHCHECK_LAST_SUCCESS] = event.data.get("now")

    hass.bus.async_listen(HEALTHCHECK_EVENT, handle_healthcheck_event)

    async_track_time_interval(
        hass, fire_healthcheck_event, timedelta(seconds=HEALTHCHECK_INTERVAL)
    )


async def handle_healthcheck_request(request: web.Request) -> web.Response:
    healthcheck_last_success = request.app[KEY_HEALTHCHECK_LAST_SUCCESS]
    healthcheck_threshold = request.app[KEY_HEALTHCHECK_THRESHOLD]

    healthcheck_delta = dt_util.utcnow() - healthcheck_last_success

    if healthcheck_delta < timedelta(
        seconds=int(HEALTHCHECK_INTERVAL * healthcheck_threshold)
    ):
        return json_response({"healthy": True})
    else:
        healthcheck_delta_seconds = healthcheck_delta.total_seconds()
        _LOGGER.error(
            f"Home-Assistant is unhealthy, last healthcheck event was observed {healthcheck_delta_seconds} seconds ago"
        )
        return json_response({"healthy": False}, status=500)
