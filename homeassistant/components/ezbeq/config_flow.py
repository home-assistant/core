"""Config flow for ezbeq Profile Loader integration."""

import logging
from typing import Any

from pyezbeq.consts import DEFAULT_PORT, DISCOVERY_ADDRESS
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .const import (
    CONF_CODEC_EXTENDED_SENSOR,
    CONF_CODEC_SENSOR,
    CONF_EDITION_SENSOR,
    CONF_JELLYFIN_CODEC_SENSOR,
    CONF_JELLYFIN_DISPLAY_TITLE_SENSOR,
    CONF_JELLYFIN_LAYOUT_SENSOR,
    CONF_JELLYFIN_PROFILE_SENSOR,
    CONF_PREFERRED_AUTHOR,
    CONF_SOURCE_MEDIA_PLAYER,
    CONF_SOURCE_TYPE,
    CONF_TITLE_SENSOR,
    CONF_TMDB_SENSOR,
    CONF_YEAR_SENSOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# User schema
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DISCOVERY_ADDRESS): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_SOURCE_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["Plex", "Jellyfin"],
                translation_key="source_type",
            )
        ),
        vol.Required(CONF_SOURCE_MEDIA_PLAYER): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player")
        ),
    }
)

# Shared schema
SHARED_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EDITION_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_TITLE_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Optional(CONF_PREFERRED_AUTHOR): str,
    }
)

# Plex schema
STEP_PLEX_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TMDB_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_YEAR_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_CODEC_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_CODEC_EXTENDED_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    }
)

# Jellyfin schema
STEP_JF_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_JELLYFIN_CODEC_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_JELLYFIN_DISPLAY_TITLE_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_JELLYFIN_PROFILE_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_JELLYFIN_LAYOUT_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    }
)


class EzBEQConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ezbeq Profile Loader."""

    VERSION = 1
    entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.ezbeq_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            schema = STEP_USER_DATA_SCHEMA
            return self.async_show_form(step_id="user", data_schema=schema)

        self.ezbeq_data.update(user_input)
        # abort on same host
        await self.async_set_unique_id(CONF_HOST)
        self._abort_if_unique_id_configured()

        return await self.async_step_entities()

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the entities step."""
        if user_input is None:
            if self.ezbeq_data[CONF_SOURCE_TYPE] == "Plex":
                schema = SHARED_DATA_SCHEMA.extend(STEP_PLEX_DATA_SCHEMA)
                return self.async_show_form(step_id="entities", data_schema=schema)
            # Jellyfin
            schema = SHARED_DATA_SCHEMA.extend(STEP_JF_DATA_SCHEMA)
            return self.async_show_form(step_id="entities", data_schema=schema)

        self.ezbeq_data.update(user_input)

        return self.async_create_entry(
            title="ezbeq Profile Loader", data=self.ezbeq_data
        )
