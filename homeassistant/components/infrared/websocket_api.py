"""Websocket API for the infrared integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DATA_COMPONENT
from .entity import InfraredEmitterEntity


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the infrared websocket API."""
    websocket_api.async_register_command(hass, ws_list_proxies)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "infrared/list",
    }
)
def ws_list_proxies(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List the available infrared proxies (emitters and receivers)."""
    component = hass.data[DATA_COMPONENT]
    ent_reg = er.async_get(hass)

    proxies: list[dict[str, Any]] = []
    for entity in component.entities:
        port_type = (
            "emitter" if isinstance(entity, InfraredEmitterEntity) else "receiver"
        )
        registry_entry = ent_reg.async_get(entity.entity_id)
        state = hass.states.get(entity.entity_id)
        proxies.append(
            {
                "entity_id": entity.entity_id,
                "device_id": registry_entry.device_id if registry_entry else None,
                "config_entry_id": (
                    registry_entry.config_entry_id if registry_entry else None
                ),
                "name": state.name if state is not None else entity.name,
                "type": port_type,
                "supported_frequencies": entity.supported_frequencies,
            }
        )

    connection.send_result(msg["id"], {"proxies": proxies})
