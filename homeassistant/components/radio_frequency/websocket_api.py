"""The Radio Frequency websocket API."""

from typing import Any

from rf_protocols import ModulationType
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DATA_COMPONENT


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the radio frequency websocket API."""
    websocket_api.async_register_command(hass, ws_list_transmitters)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "radio_frequency/list"})
@callback
def ws_list_transmitters(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the available radio frequency transmitters.

    Each transmitter is described by its entity id, the device and config
    entry it belongs to (when registered), the frequency ranges it can
    operate on and the modulation types it supports.
    """
    component = hass.data[DATA_COMPONENT]
    ent_reg = er.async_get(hass)

    transmitters: list[dict[str, Any]] = []
    for entity in component.entities:
        entry = ent_reg.async_get(entity.entity_id)
        transmitters.append(
            {
                "entity_id": entity.entity_id,
                "device_id": entry.device_id if entry else None,
                "config_entry_id": entry.config_entry_id if entry else None,
                "name": entity.name,
                "supported_frequency_ranges": [
                    [low, high] for low, high in entity.supported_frequency_ranges
                ],
                "supported_modulations": [
                    modulation.value
                    for modulation in ModulationType
                    if entity.supports_modulation(modulation)
                ],
            }
        )

    connection.send_result(msg["id"], {"transmitters": transmitters})
