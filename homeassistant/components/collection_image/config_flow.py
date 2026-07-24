"""Config flow for Collection Image integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import async_browse_media
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import MediaSelector

from .const import CONF_MEDIA, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MEDIA): MediaSelector({"accept": ["directory"]}),
    }
)


class CollectionImageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Collection Image."""

    VERSION = 1
    MINOR_VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            user_media = user_input[CONF_MEDIA]
            try:
                browse = await async_browse_media(
                    self.hass, user_media["media_content_id"]
                )
            except BrowseError as err:
                errors["media"] = "failed_browse"
                placeholders["error"] = str(err)
            else:
                if browse.children and any(
                    item.media_class == MediaClass.IMAGE for item in browse.children
                ):
                    return self.async_create_entry(
                        title=f"{browse.title or 'Unnamed'} collection",
                        data=user_input,
                    )

                errors["media"] = "selected_media_no_images"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
