"""Provides device actions for elmax-cloud."""
from __future__ import annotations

from typing import Optional

from elmax_api.model.command import Command, SceneCommand
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, ElmaxCoordinator
from .const import CONF_CONFIG_ENTRY_ID, CONF_ENDPOINT_ID

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): str,
        vol.Required(CONF_ENDPOINT_ID): str,
        vol.Required(CONF_TYPE): str,
    }
)


def _lookup_configentry_id(device_id: str, registry) -> str | None:
    entities = entity_registry.async_entries_for_device(registry, device_id)
    if len(entities) < 1:
        return None
    return entities[0].config_entry_id


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for elmax-cloud devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []
    entry_id = _lookup_configentry_id(device_id, registry)
    scenes = hass.data[DOMAIN][entry_id].data.scenes

    for scene in scenes:
        # Add actions for each entity that belongs to this integration
        base_action = {CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN}
        actions.append(
            {
                **base_action,
                CONF_CONFIG_ENTRY_ID: entry_id,
                CONF_ENDPOINT_ID: scene.endpoint_id,
                CONF_TYPE: scene.name,
            }
        )
    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    entry_id = config[CONF_CONFIG_ENTRY_ID]
    endpoint_id = config[CONF_ENDPOINT_ID]
    coordinator: ElmaxCoordinator = hass.data[DOMAIN][entry_id]
    await coordinator.http_client.execute_command(
        endpoint_id=endpoint_id, command=SceneCommand.TRIGGER_SCENE
    )
