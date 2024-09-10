"""Domika entity router."""

from typing import Any, cast

from domika_ha_framework.utils import flatten_json
import voluptuous as vol

from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import (
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant, callback

from ..const import LOGGER
from .service import get, get_single


@websocket_command(
    {
        vol.Required("type"): "domika/entity_list",
        vol.Required("domains"): list[str],
    },
)
@callback
def websocket_domika_entity_list(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika entity_list request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "entity_list", msg_id is missing')
        return

    LOGGER.debug('Got websocket message "entity_list", data: %s', msg)

    domains_list = cast(list[str], msg.get("domains"))
    entities = get(hass, domains_list)
    result = entities.to_dict()

    connection.send_result(msg_id, result)
    LOGGER.debug("Entity_list msg_id=%s", msg_id)


@websocket_command(
    {
        vol.Required("type"): "domika/entity_info",
        vol.Required("entity_id"): str,
    },
)
@callback
def websocket_domika_entity_info(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika entity_info request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "entity_info", msg_id is missing')
        return

    LOGGER.debug('Got websocket message "entity_info", data: %s', msg)

    entity_id = cast(str, msg.get("entity_id"))
    entity = get_single(hass, entity_id)
    result = entity.to_dict() if entity else {}

    connection.send_result(msg_id, result)
    LOGGER.debug("Entity_info msg_id=%s data=%s", msg_id, result)


@websocket_command(
    {
        vol.Required("type"): "domika/entity_state",
        vol.Required("entity_id"): str,
    },
)
@async_response
async def websocket_domika_entity_state(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika entity_state request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "entity_state", msg_id is missing')
        return

    LOGGER.debug('Got websocket message "entity_state", data: %s', msg)

    entity_id = cast(str, msg.get("entity_id"))
    state = hass.states.get(entity_id)
    result: tuple[dict, ...] = ({},)
    if state:
        time_updated = max(state.last_changed, state.last_updated)
        result = (
            {
                "entity_id": entity_id,
                "time_updated": time_updated,
                "attributes": flatten_json(
                    state.as_compressed_state,
                    exclude={"c", "lc", "lu"},
                ),
            },
        )
    else:
        LOGGER.error(
            "Entity_state requesting state of unknown entity: %s",
            entity_id,
        )
    connection.send_result(msg_id, result)
    LOGGER.debug("Entity_state msg_id=%s data=%s", msg_id, result)
