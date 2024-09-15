"""Config flow for ezbeq Profile Loader integration."""

import logging
from typing import Any

from httpx import HTTPStatusError, RequestError
from pyezbeq.consts import DEFAULT_PORT, DISCOVERY_ADDRESS
from pyezbeq.ezbeq import EzbeqClient
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
    DEFAULT_NAME,
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
SHARED_DATA_SCHEMA = {
    vol.Required(CONF_EDITION_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor")
    ),
    vol.Required(CONF_TITLE_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor")
    ),
    vol.Required(CONF_TMDB_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor")
    ),
    vol.Required(CONF_YEAR_SENSOR): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor")
    ),
    vol.Optional(CONF_PREFERRED_AUTHOR): str,
}

# Plex and JF have different codec schemas

# Plex schema
STEP_PLEX_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CODEC_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_CODEC_EXTENDED_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    }
).extend(SHARED_DATA_SCHEMA)

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
).extend(SHARED_DATA_SCHEMA)


class EzBEQConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ezbeq Profile Loader."""

    VERSION = 1
    entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.ezbeq_data: dict[str, Any] = {}

    async def test_connection(self) -> bool:
        """Test if we can connect to the ezbeq server."""
        client = EzbeqClient(
            host=self.ezbeq_data[CONF_HOST], port=self.ezbeq_data[CONF_PORT]
        )
        try:
            await client.get_version()
        except (HTTPStatusError, RequestError) as e:
            _LOGGER.error("Error connecting to ezbeq: %s", e)
            return False
        finally:
            await client.client.aclose()

        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        self.ezbeq_data.update(user_input)
        # abort on same host
        await self.async_set_unique_id(CONF_HOST)
        self._abort_if_unique_id_configured()

        # make sure the connection is working
        if not await self.test_connection():
            _LOGGER.error("CannotConnect error caught")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user", errors=errors, data_schema=STEP_USER_DATA_SCHEMA
            )

        return await self.async_step_entities()

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the entities step."""
        if user_input is None:
            if self.ezbeq_data[CONF_SOURCE_TYPE] == "Plex":
                return self.async_show_form(
                    step_id="entities", data_schema=STEP_PLEX_DATA_SCHEMA, errors={}
                )
            # Jellyfin
            return self.async_show_form(
                step_id="entities", data_schema=STEP_JF_DATA_SCHEMA, errors={}
            )

        self.ezbeq_data.update(user_input)

        return self.async_create_entry(title=DEFAULT_NAME, data=self.ezbeq_data)
