"""Provides device actions for Media Player."""
from typing import Any, Dict, List, Optional

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_SERVICE,
    CONF_TYPE,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import (
    DOMAIN,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from ..device_automation.const import CONF_TOGGLE, CONF_TURN_OFF, CONF_TURN_ON
from .const import (
    CONF_CLEAR_PLAYLIST,
    CONF_MEDIA_NEXT_TRACK,
    CONF_MEDIA_PAUSE,
    CONF_MEDIA_PLAY,
    CONF_MEDIA_PLAY_PAUSE,
    CONF_MEDIA_PREVIOUS_TRACK,
    CONF_MEDIA_STOP,
    CONF_SUPPORTED_FEATURES,
    CONF_VOLUME_DOWN,
    CONF_VOLUME_UP,
    SERVICE_CLEAR_PLAYLIST,
)

ACTION_TYPES: Dict[str, Dict[str, Any]] = {
    CONF_TURN_ON: {
        CONF_SERVICE: SERVICE_TURN_ON,
        CONF_SUPPORTED_FEATURES: SUPPORT_TURN_ON,
    },
    CONF_TURN_OFF: {
        CONF_SERVICE: SERVICE_TURN_OFF,
        CONF_SUPPORTED_FEATURES: SUPPORT_TURN_OFF,
    },
    CONF_TOGGLE: {
        CONF_SERVICE: SERVICE_TOGGLE,
        CONF_SUPPORTED_FEATURES: SUPPORT_TURN_ON | SUPPORT_TURN_OFF,
    },
    CONF_VOLUME_UP: {
        CONF_SERVICE: SERVICE_VOLUME_UP,
        CONF_SUPPORTED_FEATURES: SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP,
    },
    CONF_VOLUME_DOWN: {
        CONF_SERVICE: SERVICE_VOLUME_DOWN,
        CONF_SUPPORTED_FEATURES: SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP,
    },
    CONF_MEDIA_PLAY_PAUSE: {
        CONF_SERVICE: SERVICE_MEDIA_PLAY_PAUSE,
        CONF_SUPPORTED_FEATURES: SUPPORT_PLAY | SUPPORT_PAUSE,
    },
    CONF_MEDIA_PLAY: {
        CONF_SERVICE: SERVICE_MEDIA_PLAY,
        CONF_SUPPORTED_FEATURES: SUPPORT_PLAY,
    },
    CONF_MEDIA_PAUSE: {
        CONF_SERVICE: SERVICE_MEDIA_PAUSE,
        CONF_SUPPORTED_FEATURES: SUPPORT_PAUSE,
    },
    CONF_MEDIA_STOP: {
        CONF_SERVICE: SERVICE_MEDIA_STOP,
        CONF_SUPPORTED_FEATURES: SUPPORT_STOP,
    },
    CONF_MEDIA_NEXT_TRACK: {
        CONF_SERVICE: SERVICE_MEDIA_NEXT_TRACK,
        CONF_SUPPORTED_FEATURES: SUPPORT_NEXT_TRACK,
    },
    CONF_MEDIA_PREVIOUS_TRACK: {
        CONF_SERVICE: SERVICE_MEDIA_PREVIOUS_TRACK,
        CONF_SUPPORTED_FEATURES: SUPPORT_PREVIOUS_TRACK,
    },
    CONF_CLEAR_PLAYLIST: {
        CONF_SERVICE: SERVICE_CLEAR_PLAYLIST,
        CONF_SUPPORTED_FEATURES: SUPPORT_CLEAR_PLAYLIST,
    },
}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(list(ACTION_TYPES.keys())),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions for Media Player devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        state = hass.states.get(entry.entity_id)

        if state:
            supported_features = state.attributes.get(CONF_SUPPORTED_FEATURES, 0)
        else:
            supported_features = entry.supported_features

        # Add actions for each entity that belongs to this integration
        for action in ACTION_TYPES:
            action_config = ACTION_TYPES[action]
            if supported_features & action_config[CONF_SUPPORTED_FEATURES]:
                actions.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: action,
                    }
                )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Optional[Context]
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}

    config_type = config[CONF_TYPE]
    action_config = ACTION_TYPES[config_type]
    service: str = action_config[CONF_SERVICE]

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )
