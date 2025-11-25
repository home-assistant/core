"""Config flow for Photo Frame integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import async_browse_media
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import MediaSelector

from .const import CONF_MEDIA, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_MEDIA): MediaSelector({"accept": ["directory"]}),
    }
)


class PhotoFrameConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Photo Frame."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            try:
                if user_media := user_input.get(CONF_MEDIA):
                    browse = await async_browse_media(
                        self.hass, user_media.get("media_content_id")
                    )
                    if browse.children and any(
                        item.media_class == MediaClass.IMAGE for item in browse.children
                    ):
                        return self.async_create_entry(
                            title=user_input[CONF_NAME], data=user_input
                        )

                errors["media"] = "invalid_media_selected"
            except BrowseError as err:
                errors["media"] = "failed_browse"
                placeholders["error"] = str(err)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
