"""Websocket API for blueprint."""
import asyncio
import logging
from typing import Dict, Optional

import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from . import importer, models
from .const import DOMAIN

_LOGGER = logging.getLogger(__package__)


@callback
def async_setup(hass: HomeAssistant):
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, ws_list_blueprints)
    websocket_api.async_register_command(hass, ws_import_blueprint)


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/list",
    }
)
async def ws_list_blueprints(hass, connection, msg):
    """List available blueprints."""
    domain_blueprints: Optional[Dict[str, models.DomainBlueprints]] = hass.data.get(
        DOMAIN, {}
    )
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


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/import",
        vol.Required("url"): cv.url,
    }
)
async def ws_import_blueprint(hass, connection, msg):
    """Import a blueprint."""
    async with async_timeout.timeout(10):
        imported_blueprint = await importer.fetch_blueprint_from_url(hass, msg["url"])

    if imported_blueprint is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_SUPPORTED, "This url is not supported"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "url": imported_blueprint.url,
            "suggested_filename": imported_blueprint.suggested_filename,
            "raw_data": imported_blueprint.raw_data,
            "blueprint": {
                "metadata": imported_blueprint.blueprint.metadata,
            },
        },
    )
