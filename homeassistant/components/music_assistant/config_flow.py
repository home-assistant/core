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

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

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
                    updates={CONF_URL: self.server_info.base_url},
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
                        CONF_URL: self.server_info.base_url,
                    },
                )

            return self.async_show_form(
                step_id="user", data_schema=get_manual_schema(user_input), errors=errors
            )

        return self.async_show_form(step_id="user", data_schema=get_manual_schema({}))

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Mass server.

        This flow is triggered by the Zeroconf component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # abort if discovery info is not what we expect
        if "server_id" not in discovery_info.properties:
            return self.async_abort(reason="missing_server_id")
        # abort if we already have exactly this server_id
        # reload the integration if the host got updated
        self.server_info = ServerInfoMessage.from_dict(discovery_info.properties)
        await self.async_set_unique_id(self.server_info.server_id)
        self._abort_if_unique_id_configured(
            updates={CONF_URL: self.server_info.base_url},
            reload_on_update=True,
        )
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
