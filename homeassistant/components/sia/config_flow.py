"""Config flow for sia integration."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import logging
from typing import Any

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
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ADDITIONAL_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_IGNORE_TIMESTAMPS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DOMAIN,
    TITLE,
)
from .hub import SIAHub

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

DEFAULT_OPTIONS = {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: None}


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
    return validate_zones(data)


def validate_zones(data: ConfigType) -> dict[str, str] | None:
    """Validate the zones field."""
    if data[CONF_ZONES] == 0:
        return {"base": "invalid_zones"}
    return None


class SIAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sia."""

    VERSION: int = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SIAOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        self._data: ConfigType = {}
        self._options: Mapping[str, Any] = {CONF_ACCOUNTS: {}}

    async def async_step_user(self, user_input: ConfigType = None) -> FlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = validate_input(user_input)
        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id="user", data_schema=HUB_SCHEMA, errors=errors
            )
        return await self.async_handle_data_and_route(user_input)

    async def async_step_add_account(self, user_input: ConfigType = None) -> FlowResult:
        """Handle the additional accounts steps."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = validate_input(user_input)
        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id="add_account", data_schema=ACCOUNT_SCHEMA, errors=errors
            )
        return await self.async_handle_data_and_route(user_input)

    async def async_handle_data_and_route(self, user_input: ConfigType) -> FlowResult:
        """Handle the user_input, check if configured and route to the right next step or create entry."""
        self._update_data(user_input)

        self._async_abort_entries_match({CONF_PORT: self._data[CONF_PORT]})

        if user_input[CONF_ADDITIONAL_ACCOUNTS]:
            return await self.async_step_add_account()
        return self.async_create_entry(
            title=TITLE.format(self._data[CONF_PORT]),
            data=self._data,
            options=self._options,
        )

    def _update_data(self, user_input: ConfigType) -> None:
        """Parse the user_input and store in data and options attributes.

        If there is a port in the input or no data, assume it is fully new and overwrite.
        Add the default options and overwrite the zones in options.
        """
        if not self._data or user_input.get(CONF_PORT):
            self._data = {
                CONF_PORT: user_input[CONF_PORT],
                CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                CONF_ACCOUNTS: [],
            }
        account = user_input[CONF_ACCOUNT]
        self._data[CONF_ACCOUNTS].append(
            {
                CONF_ACCOUNT: account,
                CONF_ENCRYPTION_KEY: user_input.get(CONF_ENCRYPTION_KEY),
                CONF_PING_INTERVAL: user_input[CONF_PING_INTERVAL],
            }
        )
        self._options[CONF_ACCOUNTS].setdefault(account, deepcopy(DEFAULT_OPTIONS))
        self._options[CONF_ACCOUNTS][account][CONF_ZONES] = user_input[CONF_ZONES]


class SIAOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle SIA options."""

    def __init__(self, config_entry):
        """Initialize SIA options flow."""
        self.config_entry = config_entry
        self.options = deepcopy(dict(config_entry.options))
        self.hub: SIAHub | None = None
        self.accounts_todo: list = []

    async def async_step_init(self, user_input: ConfigType = None) -> FlowResult:
        """Manage the SIA options."""
        self.hub = self.hass.data[DOMAIN][self.config_entry.entry_id]
        assert self.hub is not None
        assert self.hub.sia_accounts is not None
        self.accounts_todo = [a.account_id for a in self.hub.sia_accounts]
        return await self.async_step_options()

    async def async_step_options(self, user_input: ConfigType = None) -> FlowResult:
        """Create the options step for a account."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = validate_zones(user_input)
        if user_input is None or errors is not None:
            account = self.accounts_todo[0]
            return self.async_show_form(
                step_id="options",
                description_placeholders={"account": account},
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_ZONES,
                            default=self.options[CONF_ACCOUNTS][account][CONF_ZONES],
                        ): int,
                        vol.Optional(
                            CONF_IGNORE_TIMESTAMPS,
                            default=self.options[CONF_ACCOUNTS][account][
                                CONF_IGNORE_TIMESTAMPS
                            ],
                        ): bool,
                    }
                ),
                errors=errors,
                last_step=self.last_step,
            )

        account = self.accounts_todo.pop(0)
        self.options[CONF_ACCOUNTS][account][CONF_IGNORE_TIMESTAMPS] = user_input[
            CONF_IGNORE_TIMESTAMPS
        ]
        self.options[CONF_ACCOUNTS][account][CONF_ZONES] = user_input[CONF_ZONES]
        if self.accounts_todo:
            return await self.async_step_options()
        return self.async_create_entry(title="", data=self.options)

    @property
    def last_step(self) -> bool:
        """Return if this is the last step."""
        return len(self.accounts_todo) <= 1
