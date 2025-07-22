"""Websocket commands for the Vacuum integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
import voluptuous_serialize

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.selector import ObjectSelector

from .const import DATA_COMPONENT, DOMAIN, VacuumEntityFeature

if TYPE_CHECKING:
    from . import StateVacuumEntity


@callback
def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register websocket commands."""
    websocket_api.async_register_command(hass, handle_configure)
    websocket_api.async_register_command(hass, handle_configure_schema)


def _get_schema(entity: StateVacuumEntity, frontend: bool = False) -> vol.Schema | None:
    """Get the schema for configuring a vacuum."""
    if VacuumEntityFeature.CLEAN_AREA not in entity.supported_features:
        return None

    segment_id = entity.segment_id_schema.schema
    area_mapping: Any
    if frontend:
        area_mapping = ObjectSelector()
    else:
        area_mapping = {str: [segment_id]}

    return vol.Schema({"area_mapping": area_mapping})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "vacuum/configure_schema",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def handle_configure_schema(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the schema for configuring a vacuum."""
    entity_id = msg["entity_id"]
    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None:
        connection.send_error(
            msg["id"], "entity_not_found", f"Entity {entity_id} not found"
        )
        return

    schema = voluptuous_serialize.convert(
        _get_schema(entity, frontend=True), custom_serializer=cv.custom_serializer
    )

    connection.send_result(msg["id"], {"schema": schema})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "vacuum/configure",
        vol.Required("entity_id"): str,
        vol.Required("data"): dict,
    }
)
@websocket_api.async_response
async def handle_configure(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Configure a vacuum."""
    entity_id = msg["entity_id"]
    entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    if entity is None:
        connection.send_error(
            msg["id"], "entity_not_found", f"Entity {entity_id} not found"
        )
        return

    schema = _get_schema(entity)
    if schema is None:
        connection.send_error(
            msg["id"],
            "not_supported",
            f"Entity {entity_id} does not support configuration",
        )
        return

    data = schema(msg["data"])

    ent_reg = er.async_get(hass)
    ent_reg.async_update_entity_options(entity_id, DOMAIN, data)

    connection.send_result(msg["id"])
