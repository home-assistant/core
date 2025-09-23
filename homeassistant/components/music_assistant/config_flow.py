"""Config flow for MusicAssistant integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from music_assistant_client import MusicAssistantClient
from music_assistant_client.exceptions import (
    CannotConnect,
    InvalidServerVersion,
    MusicAssistantClientException,
)
from music_assistant_models.api import ServerInfoMessage
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IGNORE, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, LOGGER

DEFAULT_URL = "http://mass.local:8095"
DEFAULT_TITLE = "Music Assistant"


def get_manual_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the manual step."""
    default_url = user_input.get(CONF_URL, DEFAULT_URL)
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=default_url): str,
        }
    )


async def get_server_info(hass: HomeAssistant, url: str) -> ServerInfoMessage:
    """Validate the user input allows us to connect."""
    async with MusicAssistantClient(
        url, aiohttp_client.async_get_clientsession(hass)
    ) as client:
        if TYPE_CHECKING:
            assert client.server_info is not None
        return client.server_info


class MusicAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MusicAssistant."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up flow instance."""
        self.server_info: ServerInfoMessage | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.server_info = await get_server_info(
                    self.hass, user_input[CONF_URL]
                )
                await self.async_set_unique_id(
                    self.server_info.server_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured(
                    updates={CONF_URL: user_input[CONF_URL]},
                    reload_on_update=True,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidServerVersion:
                errors["base"] = "invalid_server_version"
            except MusicAssistantClientException:
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=DEFAULT_TITLE,
                    data={
                        CONF_URL: user_input[CONF_URL],
                    },
                )

            return self.async_show_form(
                step_id="user", data_schema=get_manual_schema(user_input), errors=errors
            )

        return self.async_show_form(step_id="user", data_schema=get_manual_schema({}))

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Mass server.

        This flow is triggered by the Zeroconf component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # abort if discovery info is not what we expect
        if "server_id" not in discovery_info.properties:
            return self.async_abort(reason="missing_server_id")

        self.server_info = ServerInfoMessage.from_dict(discovery_info.properties)
        await self.async_set_unique_id(self.server_info.server_id)

        # Check if we already have a config entry for this server_id
        existing_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, self.server_info.server_id
        )

        if existing_entry:
            # If the entry was ignored or disabled, don't make any changes
            if existing_entry.source == SOURCE_IGNORE or existing_entry.disabled_by:
                return self.async_abort(reason="already_configured")

            # Test connectivity to the current URL first
            current_url = existing_entry.data[CONF_URL]
            try:
                await get_server_info(self.hass, current_url)
                # Current URL is working, no need to update
                return self.async_abort(reason="already_configured")
            except CannotConnect:
                # Current URL is not working, update to the discovered URL
                # and continue to discovery confirm
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        CONF_URL: self.server_info.base_url,
                    },
                )
                # Schedule reload since URL changed
                self.hass.config_entries.async_schedule_reload(existing_entry.entry_id)
        else:
            # No existing entry, proceed with normal flow
            self._abort_if_unique_id_configured()

        # Test connectivity to the discovered URL
        try:
            await get_server_info(self.hass, self.server_info.base_url)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered server."""
        if TYPE_CHECKING:
            assert self.server_info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data={
                    CONF_URL: self.server_info.base_url,
                },
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"url": self.server_info.base_url},
        )
