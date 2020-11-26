"""Websocket API for blueprint."""
import logging
from typing import Dict, Optional

import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import yaml

from . import importer, models
from .const import DOMAIN
from .errors import FileAlreadyExists

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
        vol.Required("domain"): cv.string,
    }
)
async def ws_list_blueprints(hass, connection, msg):
    """List available blueprints."""
    domain_blueprints: Optional[Dict[str, models.DomainBlueprints]] = hass.data.get(
        DOMAIN, {}
    )
    results = {}

    if msg["domain"] not in domain_blueprints:
        connection.send_result(msg["id"], results)
        return

    domain_results = await domain_blueprints[msg["domain"]].async_get_blueprints()

    for path, value in domain_results.items():
        if isinstance(value, models.Blueprint):
            results[path] = {
                "metadata": value.metadata,
            }
        else:
            results[path] = {"error": str(value)}

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
            "suggested_filename": imported_blueprint.suggested_filename,
            "raw_data": imported_blueprint.raw_data,
            "blueprint": {
                "metadata": imported_blueprint.blueprint.metadata,
            },
            "validation_errors": imported_blueprint.blueprint.validate(),
        },
    )


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/save",
        vol.Required("domain"): cv.string,
        vol.Required("path"): cv.path,
        vol.Required("yaml"): cv.string,
        vol.Optional("source_url"): cv.url,
    }
)
async def ws_save_blueprint(hass, connection, msg):
    """Save a blueprint."""

    path = msg["path"]
    domain = msg["domain"]

    domain_blueprints: Optional[Dict[str, models.DomainBlueprints]] = hass.data.get(
        DOMAIN, {}
    )

    if domain not in domain_blueprints:
        connection.send_error(
            msg["id"], websocket_api.ERR_INVALID_FORMAT, "Unsupported domain"
        )

    try:
        blueprint = models.Blueprint(
            yaml.parse_yaml(msg["yaml"]), expected_domain=domain
        )
        if "source_url" in msg:
            blueprint.update_metadata(source_url=msg["source_url"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
        return

    try:
        await domain_blueprints[domain].async_add_blueprint(blueprint, path)
    except FileAlreadyExists:
        connection.send_error(msg["id"], "already_exists", "File already exists")
        return
    except OSError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return

    connection.send_result(
        msg["id"],
    )


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/delete",
        vol.Required("domain"): cv.string,
        vol.Required("path"): cv.path,
    }
)
async def ws_delete_blueprint(hass, connection, msg):
    """Delete a blueprint."""

    path = msg["path"]
    domain = msg["domain"]

    domain_blueprints: Optional[Dict[str, models.DomainBlueprints]] = hass.data.get(
        DOMAIN, {}
    )

    if domain not in domain_blueprints:
        connection.send_error(
            msg["id"], websocket_api.ERR_INVALID_FORMAT, "Unsupported domain"
        )

    try:
        await domain_blueprints[domain].async_remove_blueprint(path)
    except OSError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return

    connection.send_result(
        msg["id"],
    )
