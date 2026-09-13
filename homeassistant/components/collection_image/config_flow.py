"""Config flow for Collection Image integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import URI_SCHEME, async_browse_media
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import MediaSelector

from .const import CONF_MEDIA, DOMAIN

IMAGE_MEDIA_URI = f"{URI_SCHEME}{IMAGE_DOMAIN}"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MEDIA): MediaSelector(
            {"accept": ["directory"], "multiple": True}
        ),
    }
)


class CollectionImageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Collection Image."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        found_pictures = False
        title = "Unnamed collection"
        if user_input is not None:
            user_media_list = user_input[CONF_MEDIA]
            for user_media in user_media_list:
                if user_media["media_content_id"] == IMAGE_MEDIA_URI:
                    errors["media"] = "invalid_selection"
                    placeholders["error"] = IMAGE_MEDIA_URI
                    break
                try:
                    browse = await async_browse_media(
                        self.hass, user_media["media_content_id"]
                    )
                except BrowseError as err:
                    errors["media"] = "failed_browse"
                    placeholders["error"] = str(err)
                    break
                else:
                    if (
                        not found_pictures
                        and browse.children
                        and any(
                            item.media_class == MediaClass.IMAGE
                            for item in browse.children
                        )
                    ):
                        found_pictures = True
                        if browse.title:
                            title = f"{browse.title} collection"
            if "media" not in errors:
                if found_pictures:
                    return self.async_create_entry(
                        title=title,
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
