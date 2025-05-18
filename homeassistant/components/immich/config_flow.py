"""Config flow for the Immich integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aioimmich import Immich
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichUnauthorizedError
from aioimmich.server.models import ImmichServerAbout
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_VERIFY_SSL, DOMAIN


class InvalidUrl(HomeAssistantError):
    """Error to indicate invalid URL."""


_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_API_KEY): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


def _parse_url(url: str) -> tuple[str, int, bool]:
    """Parse the URL and return host, port, and ssl."""
    parsed_url = URL(url)
    if (
        (host := parsed_url.host) is None
        or (port := parsed_url.port) is None
        or (scheme := parsed_url.scheme) is None
    ):
        raise InvalidUrl
    return host, port, scheme == "https"


async def check_server_info(
    hass: HomeAssistant, host: str, port: int, ssl: bool, verify_ssl: bool, api_key: str
) -> ImmichServerAbout:
    """Try to read server info."""
    session = async_get_clientsession(hass, verify_ssl)
    immich = Immich(session, api_key, host, port, ssl)
    return await immich.server.async_get_about_info()


class ImmichConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Immich."""

    VERSION = 1

    _name: str
    _current_data: Mapping[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                (host, port, ssl) = _parse_url(user_input[CONF_URL])
            except InvalidUrl:
                errors[CONF_URL] = "invalid_url"
            else:
                self._async_abort_entries_match({CONF_HOST: host})
                try:
                    await check_server_info(
                        self.hass,
                        host,
                        port,
                        ssl,
                        user_input[CONF_VERIFY_SSL],
                        user_input[CONF_API_KEY],
                    )
                except ImmichUnauthorizedError:
                    errors["base"] = "invalid_auth"
                except CONNECT_ERRORS:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_URL],
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_SSL: ssl,
                            CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                            CONF_API_KEY: user_input[CONF_API_KEY],
                        },
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger a reauthentication flow."""
        self._current_data = entry_data
        self._name = entry_data[CONF_HOST]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        errors = {}

        if user_input is not None:
            try:
                await check_server_info(
                    self.hass,
                    self._current_data[CONF_HOST],
                    self._current_data[CONF_PORT],
                    self._current_data[CONF_SSL],
                    self._current_data[CONF_VERIFY_SSL],
                    user_input[CONF_API_KEY],
                )
            except ImmichUnauthorizedError:
                errors["base"] = "invalid_auth"
            except CONNECT_ERRORS:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            description_placeholders={"name": self._name},
            errors=errors,
        )
