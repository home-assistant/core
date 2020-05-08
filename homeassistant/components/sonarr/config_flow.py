"""Config flow for Sonarr."""
import logging
from typing import Any, Dict, Optional

from sonarr import Sonarr, SonarrAccessRestricted, SonarrError
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_BASE_PATH,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WANTED_MAX_ITEMS,
)
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_UNKNOWN = "unknown"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_BASE_PATH, default=DEFAULT_BASE_PATH): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


async def validate_input(hass: HomeAssistantType, data: dict) -> Dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)

    sonarr = Sonarr(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        api_key=data[CONF_API_KEY],
        base_path=data[CONF_BASE_PATH],
        tls=data[CONF_SSL],
        verify_ssl=data[CONF_VERIFY_SSL],
        session=session,
    )

    await sonarr.update()

    return True


class SonarrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonarr."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SonarrOptionsFlowHandler(config_entry)

    async def async_step_import(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by configuration file."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        try:
            await validate_input(self.hass, user_input)
        except SonarrAccessRestricted:
            return self._show_setup_form({"base": ERROR_INVALID_AUTH})
        except SonarrError:
            return self._show_setup_form({"base": ERROR_CANNOT_CONNECT})
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason=ERROR_UNKNOWN)

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors or {},
        )


class SonarrOptionsFlowHandler(OptionsFlow):
    """Handle Sonarr client options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[ConfigType] = None):
        """Manage Sonarr options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_UPCOMING_DAYS,
                default=self.config_entry.options.get(
                    CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
                ),
            ): int,
            vol.Optional(
                CONF_WANTED_MAX_ITEMS,
                default=self.config_entry.options.get(
                    CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
