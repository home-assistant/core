"""Config flow for the LibreNMS integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiolibrenms import Librenms
from aiolibrenms.const import CONNECT_ERRORS
from aiolibrenms.exceptions import LibrenmsUnauthenticatedError
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


async def check_connection(
    hass: HomeAssistant, host: str, port: int, ssl: bool, verify_ssl: bool, api_key: str
) -> None:
    """Test connection."""
    session = async_get_clientsession(hass, verify_ssl)
    lnms = Librenms(session, api_key, host, port, ssl)
    await lnms.system.async_get_system_info()


class LibrenmsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LibreNMS."""

    VERSION = 1

    _name: str
    _current_data: Mapping[str, Any]

    @override
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
                self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})
                try:
                    await check_connection(
                        self.hass,
                        host,
                        port,
                        ssl,
                        user_input[CONF_VERIFY_SSL],
                        user_input[CONF_API_KEY],
                    )
                except LibrenmsUnauthenticatedError:
                    errors["base"] = "invalid_auth"
                except CONNECT_ERRORS:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=host,
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
