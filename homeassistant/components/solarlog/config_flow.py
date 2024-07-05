"""Config flow for solarlog integration."""

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import ParseResult, urlparse

from solarlog_cli.solarlog_connector import SolarLogConnector
from solarlog_cli.solarlog_exceptions import SolarLogConnectionError, SolarLogError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def solarlog_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return {
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class SolarLogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for solarlog."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        if host in solarlog_entries(self.hass):
            return True
        return False

    def _parse_url(self, host: str) -> str:
        """Return parsed host url."""
        url = urlparse(host, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        url = ParseResult("http", netloc, path, *url[3:])
        return url.geturl()

    async def _test_connection(self, host):
        """Check if we can connect to the Solar-Log device."""
        solarlog = SolarLogConnector(host)
        try:
            await solarlog.test_connection()
        except SolarLogConnectionError:
            self._errors = {CONF_HOST: "cannot_connect"}
            return False
        except SolarLogError:
            self._errors = {CONF_HOST: "unknown"}
            return False
        finally:
            await solarlog.client.close()

        return True

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            # set some defaults in case we need to return to the form
            user_input[CONF_NAME] = slugify(user_input[CONF_NAME])
            user_input[CONF_HOST] = self._parse_url(user_input[CONF_HOST])

            if self._host_in_configuration_exists(user_input[CONF_HOST]):
                self._errors[CONF_HOST] = "already_configured"
            elif await self._test_connection(user_input[CONF_HOST]):
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_HOST] = DEFAULT_HOST

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST, DEFAULT_HOST)
                    ): str,
                    vol.Required("extended_data", default=False): bool,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry."""

        user_input = {
            CONF_HOST: DEFAULT_HOST,
            CONF_NAME: DEFAULT_NAME,
            "extended_data": False,
            **user_input,
        }

        user_input[CONF_HOST] = self._parse_url(user_input[CONF_HOST])

        if self._host_in_configuration_exists(user_input[CONF_HOST]):
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""

        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if TYPE_CHECKING:
            assert entry is not None

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                reason="reconfigure_successful",
                data={**entry.data, **user_input},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "extended_data", default=entry.data["extended_data"]
                    ): bool,
                }
            ),
        )
