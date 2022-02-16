"""Media player actions."""

from typing import cast

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, script
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN,
    SERVICE_PLAY_MEDIA,
)

PLAY_MEDIA_SCHEMA = vol.Schema(
    {
        vol.Required("media_player.play_media"): vol.Schema(
            {
                "entity_id": cv.entity_domain(DOMAIN),
                "media_content_id": str,
                "media_content_type": str,
            }
        )
    }
)

PLATFORM_SCHEMA = cv.single_key_schemas(
    {
        "media_player.play_media": PLAY_MEDIA_SCHEMA,
    }
)


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    return cast(ConfigType, PLATFORM_SCHEMA(config))


async def async_run_action(
    hass: HomeAssistant, config: ConfigType, info: script.ScriptInfo
) -> None:
    """Run action."""
    action_key, action_conf = next(c for c in config.items())
    action = action_key.partition(".")[2]

    if action == "play_media":
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: action_conf[ATTR_ENTITY_ID],
                ATTR_MEDIA_CONTENT_TYPE: action_conf[ATTR_MEDIA_CONTENT_TYPE],
                ATTR_MEDIA_CONTENT_ID: action_conf[ATTR_MEDIA_CONTENT_ID],
            },
            context=info.context,
            blocking=True,
        )
        return

    raise ValueError(f"Unknown action {action_key} specified")
