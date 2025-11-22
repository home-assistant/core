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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, LOGGER

DEFAULT_TITLE = "Music Assistant"
DEFAULT_URL = "http://mass.local:8095"


STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_URL): str})


async def _get_server_info(hass: HomeAssistant, url: str) -> ServerInfoMessage:
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
        self.url: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                server_info = await _get_server_info(self.hass, user_input[CONF_URL])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidServerVersion:
                errors["base"] = "invalid_server_version"
            except MusicAssistantClientException:
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    server_info.server_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured(
                    updates={CONF_URL: user_input[CONF_URL]}
                )

                return self.async_create_entry(
                    title=DEFAULT_TITLE,
                    data={CONF_URL: user_input[CONF_URL]},
                )

        suggested_values = user_input
        if suggested_values is None:
            suggested_values = {CONF_URL: DEFAULT_URL}

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a zeroconf discovery for a Music Assistant server."""
        try:
            server_info = ServerInfoMessage.from_dict(discovery_info.properties)
        except LookupError:
            return self.async_abort(reason="invalid_discovery_info")

        self.url = server_info.base_url

        await self.async_set_unique_id(server_info.server_id)
        self._abort_if_unique_id_configured(updates={CONF_URL: self.url})

        try:
            await _get_server_info(self.hass, self.url)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered server."""
        if TYPE_CHECKING:
            assert self.url is not None

        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data={CONF_URL: self.url},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"url": self.url},
        )
