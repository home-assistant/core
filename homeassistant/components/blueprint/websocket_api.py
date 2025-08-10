"""Websocket API for blueprint."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import functools
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import yaml as yaml_util

from . import importer, models
from .const import DOMAIN
from .errors import BlueprintException, FailedToLoad, FileAlreadyExists
from .schemas import BLUEPRINT_SCHEMA


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, ws_delete_blueprint)
    websocket_api.async_register_command(hass, ws_import_blueprint)
    websocket_api.async_register_command(hass, ws_list_blueprints)
    websocket_api.async_register_command(hass, ws_save_blueprint)
    websocket_api.async_register_command(hass, ws_substitute_blueprint)


def _ws_with_blueprint_domain(
    func: Callable[
        [
            HomeAssistant,
            websocket_api.ActiveConnection,
            dict[str, Any],
            models.DomainBlueprints,
        ],
        Coroutine[Any, Any, None],
    ],
) -> websocket_api.AsyncWebSocketCommandHandler:
    """Decorate a function to pass in the domain blueprints."""

    @functools.wraps(func)
    async def with_domain_blueprints(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        domain_blueprints: models.DomainBlueprints | None = hass.data.get(
            DOMAIN, {}
        ).get(msg["domain"])
        if domain_blueprints is None:
            connection.send_error(
                msg["id"], websocket_api.ERR_INVALID_FORMAT, "Unsupported domain"
            )
            return

        await func(hass, connection, msg, domain_blueprints)

    return with_domain_blueprints


@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/list",
        vol.Required("domain"): cv.string,
    }
)
@websocket_api.async_response
async def ws_list_blueprints(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List available blueprints."""
    domain_blueprints: dict[str, models.DomainBlueprints] = hass.data.get(DOMAIN, {})
    results: dict[str, Any] = {}

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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/import",
        vol.Required("url"): cv.url,
    }
)
@websocket_api.async_response
async def ws_import_blueprint(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Import a blueprint."""
    async with asyncio.timeout(10):
        imported_blueprint = await importer.fetch_blueprint_from_url(hass, msg["url"])

    if imported_blueprint is None:
        connection.send_error(  # type: ignore[unreachable]
            msg["id"], websocket_api.ERR_NOT_SUPPORTED, "This url is not supported"
        )
        return

    # Check it exists and if so, which automations are using it
    domain = imported_blueprint.blueprint.metadata["domain"]
    domain_blueprints: models.DomainBlueprints | None = hass.data.get(DOMAIN, {}).get(
        domain
    )
    if domain_blueprints is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_INVALID_FORMAT, "Unsupported domain"
        )
        return

    suggested_path = f"{imported_blueprint.suggested_filename}.yaml"
    try:
        exists = bool(await domain_blueprints.async_get_blueprint(suggested_path))
    except FailedToLoad:
        exists = False

    connection.send_result(
        msg["id"],
        {
            "suggested_filename": imported_blueprint.suggested_filename,
            "raw_data": imported_blueprint.raw_data,
            "blueprint": {
                "metadata": imported_blueprint.blueprint.metadata,
            },
            "validation_errors": imported_blueprint.blueprint.validate(),
            "exists": exists,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/save",
        vol.Required("domain"): cv.string,
        vol.Required("path"): cv.path,
        vol.Required("yaml"): cv.string,
        vol.Optional("source_url"): cv.url,
        vol.Optional("allow_override"): bool,
    }
)
@websocket_api.async_response
@_ws_with_blueprint_domain
async def ws_save_blueprint(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    domain_blueprints: models.DomainBlueprints,
) -> None:
    """Save a blueprint."""

    path = msg["path"]
    domain = msg["domain"]

    try:
        yaml_data = cast(dict[str, Any], yaml_util.parse_yaml(msg["yaml"]))
        blueprint = models.Blueprint(
            yaml_data, expected_domain=domain, schema=BLUEPRINT_SCHEMA
        )
        if "source_url" in msg:
            blueprint.update_metadata(source_url=msg["source_url"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
        return

    if not path.endswith(".yaml"):
        path = f"{path}.yaml"

    try:
        overrides_existing = await domain_blueprints.async_add_blueprint(
            blueprint, path, allow_override=msg.get("allow_override", False)
        )
    except FileAlreadyExists:
        connection.send_error(msg["id"], "already_exists", "File already exists")
        return
    except OSError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return

    connection.send_result(
        msg["id"],
        {
            "overrides_existing": overrides_existing,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/delete",
        vol.Required("domain"): cv.string,
        vol.Required("path"): cv.path,
    }
)
@websocket_api.async_response
@_ws_with_blueprint_domain
async def ws_delete_blueprint(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    domain_blueprints: models.DomainBlueprints,
) -> None:
    """Delete a blueprint."""
    try:
        await domain_blueprints.async_remove_blueprint(msg["path"])
    except OSError as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return

    connection.send_result(
        msg["id"],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "blueprint/substitute",
        vol.Required("domain"): cv.string,
        vol.Required("path"): cv.path,
        vol.Required("input"): dict,
    }
)
@websocket_api.async_response
@_ws_with_blueprint_domain
async def ws_substitute_blueprint(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    domain_blueprints: models.DomainBlueprints,
) -> None:
    """Process a blueprinted config to allow editing."""

    blueprint_config = {"use_blueprint": {"path": msg["path"], "input": msg["input"]}}

    try:
        blueprint_inputs = await domain_blueprints.async_inputs_from_config(
            blueprint_config
        )
    except BlueprintException as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return

    try:
        config = blueprint_inputs.async_substitute()
    except yaml_util.UndefinedSubstitution as err:
        connection.send_error(msg["id"], websocket_api.ERR_UNKNOWN_ERROR, str(err))
        return

    connection.send_result(msg["id"], {"substituted_config": config})
