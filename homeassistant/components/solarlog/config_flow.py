"""Config flow for solarlog integration."""

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import ParseResult, urlparse

from solarlog_cli.solarlog_connector import SolarLogConnector
from solarlog_cli.solarlog_exceptions import SolarLogConnectionError, SolarLogError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.util import slugify

from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SolarLogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for solarlog."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}

    def _parse_url(self, host: str) -> str:
        """Return parsed host url."""
        url = urlparse(host, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        url = ParseResult("http", netloc, path, *url[3:])
        return url.geturl()

    async def _test_connection(self, host: str) -> bool:
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            user_input[CONF_HOST] = self._parse_url(user_input[CONF_HOST])

            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            user_input[CONF_NAME] = slugify(user_input[CONF_NAME])

            if await self._test_connection(user_input[CONF_HOST]):
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        else:
            user_input = {CONF_NAME: DEFAULT_NAME, CONF_HOST: DEFAULT_HOST}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required("extended_data", default=False): bool,
                }
            ),
            errors=self._errors,
        )

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
