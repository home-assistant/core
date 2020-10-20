"""Websocket API for blueprint."""
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from . import models
from .const import BLUEPRINT_FOLDER, DOMAIN

_LOGGER = logging.getLogger(__package__)


@callback
def async_setup(hass: HomeAssistant):
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, ws_list_blueprints)


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/list",
    }
)
async def ws_list_blueprints(hass, connection, msg):
    """List available blueprints."""
    domain_blueprints: Optional[Dict[str, models.DomainBlueprints]] = hass.data.get(
        DOMAIN
    )

    if domain_blueprints is None:
        connection.send_result(msg["id"], {1: 2})
        return

    blueprint_folder = Path(hass.config.path(BLUEPRINT_FOLDER))

    if not blueprint_folder.exists():
        connection.send_result(msg["id"], {2: 3})
        return

    results = {}

    for domain, domain_results in zip(
        domain_blueprints,
        await asyncio.gather(
            *[db.async_get_blueprints() for db in domain_blueprints.values()]
        ),
    ):
        for path, value in domain_results.items():
            if isinstance(value, models.Blueprint):
                domain_results[path] = {
                    "metadata": value.metadata,
                }
            else:
                domain_results[path] = {"error": str(value)}

        results[domain] = domain_results

    connection.send_result(msg["id"], results)
