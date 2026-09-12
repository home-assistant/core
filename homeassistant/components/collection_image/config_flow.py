"""Config flow for Collection Image integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import URI_SCHEME, async_browse_media
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
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


async def _async_validate_media(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> tuple[str | None, dict[str, str], dict[str, str]]:
    """Validate selected directories and return title and form errors."""
    errors: dict[str, str] = {}
    placeholders: dict[str, str] = {}
    found_pictures = False
    title = "Unnamed collection"

    for user_media in user_input[CONF_MEDIA]:
        if user_media["media_content_id"] == IMAGE_MEDIA_URI:
            errors[CONF_MEDIA] = "invalid_selection"
            placeholders["error"] = IMAGE_MEDIA_URI
            break

        try:
            browse = await async_browse_media(
                hass,
                user_media["media_content_id"],
            )
        except BrowseError as err:
            errors[CONF_MEDIA] = "failed_browse"
            placeholders["error"] = str(err)
            break

        if (
            not found_pictures
            and browse.children
            and any(item.media_class == MediaClass.IMAGE for item in browse.children)
        ):
            found_pictures = True
            if browse.title:
                title = f"{browse.title} collection"

    if not errors and not found_pictures:
        errors[CONF_MEDIA] = "selected_media_no_images"

    return (title if not errors else None), errors, placeholders


def _get_media(entry: ConfigEntry) -> list[Any]:
    """Get media from options, or legacy config-entry data. Migrate to array if scalar."""
    media: Any
    if CONF_MEDIA in entry.options:
        media = entry.options[CONF_MEDIA]
    else:
        media = entry.data[CONF_MEDIA]

    return media if isinstance(media, list) else [media]


class CollectionImageOptionsFlow(OptionsFlowWithReload):
    """Handle Collection Image options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Edit the collection's media directories."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            _title, errors, placeholders = await _async_validate_media(
                self.hass,
                user_input,
            )
            if not errors:
                return self.async_create_entry(
                    title="",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {CONF_MEDIA: _get_media(self.config_entry)},
            ),
            errors=errors,
            description_placeholders=placeholders,
        )


class CollectionImageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Collection Image."""

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        _config_entry: ConfigEntry,
    ) -> CollectionImageOptionsFlow:
        """Return the options flow."""
        return CollectionImageOptionsFlow()

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            title, errors, placeholders = await _async_validate_media(
                self.hass,
                user_input,
            )
            if title is not None:
                return self.async_create_entry(
                    title=title,
                    data={},
                    options=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input,
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
