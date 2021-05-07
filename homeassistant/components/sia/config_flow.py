"""Config flow for sia integration."""
from __future__ import annotations

import logging

from pysiaalarm import (
    InvalidAccountFormatError,
    InvalidAccountLengthError,
    InvalidKeyFormatError,
    InvalidKeyLengthError,
    SIAAccount,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT, CONF_PROTOCOL
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ADDITIONAL_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DOMAIN,
    TITLE,
)

_LOGGER = logging.getLogger(__name__)


HUB_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT): int,
        vol.Optional(CONF_PROTOCOL, default="TCP"): vol.In(["TCP", "UDP"]),
        vol.Required(CONF_ACCOUNT): str,
        vol.Optional(CONF_ENCRYPTION_KEY): str,
        vol.Required(CONF_PING_INTERVAL, default=1): int,
        vol.Required(CONF_ZONES, default=1): int,
        vol.Optional(CONF_ADDITIONAL_ACCOUNTS, default=False): bool,
    }
)

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT): str,
        vol.Optional(CONF_ENCRYPTION_KEY): str,
        vol.Required(CONF_PING_INTERVAL, default=1): int,
        vol.Required(CONF_ZONES, default=1): int,
        vol.Optional(CONF_ADDITIONAL_ACCOUNTS, default=False): bool,
    }
)


def validate_input(data: ConfigType) -> dict[str, str] | None:
    """Validate the input by the user."""
    try:
        SIAAccount.validate_account(data[CONF_ACCOUNT], data.get(CONF_ENCRYPTION_KEY))
    except InvalidKeyFormatError:
        return {"base": "invalid_key_format"}
    except InvalidKeyLengthError:
        return {"base": "invalid_key_length"}
    except InvalidAccountFormatError:
        return {"base": "invalid_account_format"}
    except InvalidAccountLengthError:
        return {"base": "invalid_account_length"}
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception from SIAAccount: %s", exc)
        return {"base": "unknown"}
    if not 1 <= data[CONF_PING_INTERVAL] <= 1440:
        return {"base": "invalid_ping"}
    if data[CONF_ZONES] == 0:
        return {"base": "invalid_zones"}
    return None


class SIAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sia."""

    VERSION: int = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data: ConfigType = {}

    async def async_step_user(self, user_input: ConfigType = None):
        """Handle the initial user step."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = validate_input(user_input)
        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id="user", data_schema=HUB_SCHEMA, errors=errors
            )
        return await self.async_handle_data_and_route(user_input)

    async def async_step_add_account(self, user_input: ConfigType = None):
        """Handle the additional accounts steps."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = validate_input(user_input)
        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id="add_account", data_schema=ACCOUNT_SCHEMA, errors=errors
            )
        return await self.async_handle_data_and_route(user_input)

    async def async_handle_data_and_route(self, user_input: ConfigType):
        """Handle the user_input, check if configured and route to the right next step or create entry."""
        self._update_data(user_input)
        if self._data and self._port_already_configured():
            return self.async_abort(reason="already_configured")

        if user_input[CONF_ADDITIONAL_ACCOUNTS]:
            return await self.async_step_add_account()
        return self.async_create_entry(
            title=TITLE.format(self._data[CONF_PORT]),
            data=self._data,
        )

    def _update_data(self, user_input: ConfigType) -> None:
        """Parse the user_input and store in data attribute. If there is a port in the input, assume it is fully new and overwrite."""
        if self._data and not user_input.get(CONF_PORT):
            add_data = user_input.copy()
            add_data.pop(CONF_ADDITIONAL_ACCOUNTS)
            self._data[CONF_ACCOUNTS].append(add_data)
            return
        self._data = {
            CONF_PORT: user_input[CONF_PORT],
            CONF_PROTOCOL: user_input[CONF_PROTOCOL],
            CONF_ACCOUNTS: [
                {
                    CONF_ACCOUNT: user_input[CONF_ACCOUNT],
                    CONF_ENCRYPTION_KEY: user_input.get(CONF_ENCRYPTION_KEY),
                    CONF_PING_INTERVAL: user_input[CONF_PING_INTERVAL],
                    CONF_ZONES: user_input[CONF_ZONES],
                }
            ],
        }

    def _port_already_configured(self):
        """See if we already have a SIA entry matching the port."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_PORT] == self._data[CONF_PORT]:
                return True
        return False
