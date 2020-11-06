"""Websocket API for blueprint."""
import asyncio
import logging
import pathlib
from typing import Dict, Optional

import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from . import importer, models
from .const import BLUEPRINT_FOLDER, DOMAIN

_LOGGER = logging.getLogger(__package__)


@callback
def async_setup(hass: HomeAssistant):
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, ws_list_blueprints)
    websocket_api.async_register_command(hass, ws_import_blueprint)
    websocket_api.async_register_command(hass, ws_save_blueprint)
    websocket_api.async_register_command(hass, ws_delete_blueprint)


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


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/save",
        vol.Required("domain"): cv.string,
        vol.Required("filename"): cv.string,
        vol.Required("data"): cv.string,
    }
)
async def ws_save_blueprint(hass, connection, msg):
    """Save a blueprint."""

    filename = msg["filename"]
    domain = msg["domain"]

    blueprint_path = pathlib.Path(
        hass.config.path(BLUEPRINT_FOLDER, domain, f"{filename}.yaml")
    )

    if blueprint_path.exists():
        connection.send_error(
            msg["id"], websocket_api.ERR_UNKNOWN_ERROR, "File already exists"
        )
        return

    def createFile():
        """Create blueprint file."""
        blueprint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(blueprint_path, "x") as file:
            file.write(msg["data"])

    try:
        await hass.async_add_executor_job(createFile)
    except OSError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return

    domain_blueprints: Optional[Dict[str, models.DomainBlueprints]] = hass.data.get(
        DOMAIN, {}
    )
    domain_blueprints[domain].async_reset_cache()

    connection.send_result(
        msg["id"],
    )


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/delete",
        vol.Required("domain"): cv.string,
        vol.Required("path"): cv.string,
    }
)
async def ws_delete_blueprint(hass, connection, msg):
    """Delete a blueprint."""

    path = msg["path"]
    domain = msg["domain"]

    blueprint_path = pathlib.Path(hass.config.path(BLUEPRINT_FOLDER, domain, path))

    try:
        await hass.async_add_executor_job(blueprint_path.unlink)
    except OSError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return

    domain_blueprints: Optional[Dict[str, models.DomainBlueprints]] = hass.data.get(
        DOMAIN, {}
    )
    domain_blueprints[domain].async_reset_cache()

    connection.send_result(
        msg["id"],
    )
