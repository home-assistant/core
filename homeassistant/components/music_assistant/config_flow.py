"""Config flow for MusicAssistant integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from music_assistant.client import MusicAssistantClient
from music_assistant.client.exceptions import (
    CannotConnect,
    InvalidServerVersion,
    MusicAssistantClientException,
)
from music_assistant.common.models.api import ServerInfoMessage
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
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

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        if user_input is not None:
            errors = {}
            self.server_info = await get_server_info(self.hass, user_input[CONF_URL])
            try:
                await self.async_set_unique_id(self.server_info.server_id)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidServerVersion:
                errors["base"] = "invalid_server_version"
            except MusicAssistantClientException:
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            return self.async_show_form(
                step_id="manual",
                data_schema=get_manual_schema(user_input),
                errors=errors,
            )
        return await self._async_create_entry_or_abort()

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
        server_id = discovery_info.properties["server_id"]
        base_url = discovery_info.properties["base_url"]
        await self.async_set_unique_id(server_id)
        self._abort_if_unique_id_configured(
            updates={CONF_URL: base_url},
            reload_on_update=True,
        )
        self.server_info = ServerInfoMessage.from_dict(discovery_info.properties)
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered server."""
        if TYPE_CHECKING:
            assert self.server_info is not None
        if user_input is not None:
            # Check that we can connect to the address.
            try:
                await get_server_info(self.hass, self.server_info.base_url)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
            return await self._async_create_entry_or_abort()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"url": self.server_info.base_url},
        )

    async def _async_create_entry_or_abort(self) -> ConfigFlowResult:
        """Return a config entry for the flow or abort if already configured."""
        assert self.server_info is not None

        for config_entry in self._async_current_entries():
            if config_entry.unique_id != self.server_info.server_id:
                continue
            self.hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    CONF_URL: self.server_info.base_url,
                },
                title=DEFAULT_TITLE,
            )
            await self.hass.config_entries.async_reload(config_entry.entry_id)
            raise AbortFlow("reconfiguration_successful")

        # Abort any other flows that may be in progress
        for progress in self._async_in_progress():
            self.hass.config_entries.flow.async_abort(progress["flow_id"])

        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data={
                CONF_URL: self.server_info.base_url,
            },
        )
