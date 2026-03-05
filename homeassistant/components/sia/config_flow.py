"""Config flow for sia integration."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import logging
from typing import Any

from osbornehoffman import (
    InvalidAccountFormatError as OHInvalidAccountFormatError,
    InvalidAccountLengthError as OHInvalidAccountLengthError,
    InvalidPanelIDFormatError,
    InvalidPanelIDLengthError,
    OHAccount,
)
from pysiaalarm import (
    InvalidAccountFormatError,
    InvalidAccountLengthError,
    InvalidKeyFormatError,
    InvalidKeyLengthError,
    SIAAccount,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PORT, CONF_PROTOCOL
from homeassistant.core import callback

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_ADDITIONAL_ACCOUNTS,
    CONF_ENCRYPTION_KEY,
    CONF_FORWARD_HEARTBEAT,
    CONF_IGNORE_TIMESTAMPS,
    CONF_PANEL_ID,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DOMAIN,
    PROTOCOL_OH,
    TITLE,
)
from .hub import SIAHub

_LOGGER = logging.getLogger(__name__)

HUB_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT): int,
        vol.Optional(CONF_PROTOCOL, default="TCP"): vol.In(["TCP", "UDP", "OH"]),
    }
)

SIA_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT): str,
        vol.Optional(CONF_ENCRYPTION_KEY): str,
        vol.Required(CONF_PING_INTERVAL, default=1): int,
        vol.Required(CONF_ZONES, default=1): int,
        vol.Optional(CONF_ADDITIONAL_ACCOUNTS, default=False): bool,
    }
)

OH_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT): str,
        vol.Optional(CONF_PANEL_ID): str,
        vol.Optional(CONF_FORWARD_HEARTBEAT, default=True): bool,
        vol.Required(CONF_PING_INTERVAL, default=1): int,
        vol.Required(CONF_ZONES, default=1): int,
        vol.Optional(CONF_ADDITIONAL_ACCOUNTS, default=False): bool,
    }
)

DEFAULT_OPTIONS = {CONF_IGNORE_TIMESTAMPS: False, CONF_ZONES: None}


def validate_input(
    data: dict[str, Any], protocol: str | None = None
) -> dict[str, str] | None:
    """Validate the input by the user."""
    effective_protocol = protocol or data.get(CONF_PROTOCOL, "TCP")
    if effective_protocol == PROTOCOL_OH:
        return _validate_oh_input(data)
    return _validate_sia_input(data)


def _validate_sia_input(data: dict[str, Any]) -> dict[str, str] | None:
    """Validate SIA protocol input."""
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
    except Exception:
        _LOGGER.exception("Unexpected exception from SIAAccount")
        return {"base": "unknown"}
    if not 1 <= data[CONF_PING_INTERVAL] <= 1440:
        return {"base": "invalid_ping"}
    return validate_zones(data)


def _validate_oh_input(data: dict[str, Any]) -> dict[str, str] | None:
    """Validate OH protocol input."""
    try:
        OHAccount.validate_account(
            account_id=data[CONF_ACCOUNT],
            panel_id=data.get(CONF_PANEL_ID),
        )
    except OHInvalidAccountFormatError:
        return {"base": "invalid_account_format"}
    except OHInvalidAccountLengthError:
        return {"base": "invalid_account_length"}
    except InvalidPanelIDFormatError:
        return {"base": "invalid_panel_id_format"}
    except InvalidPanelIDLengthError:
        return {"base": "invalid_panel_id_length"}
    except Exception:
        _LOGGER.exception("Unexpected exception from OHAccount")
        return {"base": "unknown"}
    if not 1 <= data[CONF_PING_INTERVAL] <= 1440:
        return {"base": "invalid_ping"}
    return validate_zones(data)


def validate_zones(data: dict[str, Any]) -> dict[str, str] | None:
    """Validate the zones field."""
    if data[CONF_ZONES] == 0:
        return {"base": "invalid_zones"}
    return None


class SIAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sia."""

    VERSION: int = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SIAOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SIAOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._options: Mapping[str, Any] = {CONF_ACCOUNTS: {}}
        self._protocol: str = "TCP"

    def _get_account_schema(self) -> vol.Schema:
        """Return the account schema for the selected protocol."""
        if self._protocol == PROTOCOL_OH:
            return OH_ACCOUNT_SCHEMA
        return SIA_ACCOUNT_SCHEMA

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: select port and protocol."""
        if user_input is not None:
            self._protocol = user_input.get(CONF_PROTOCOL, "TCP")
            self._data = {
                CONF_PORT: user_input[CONF_PORT],
                CONF_PROTOCOL: self._protocol,
                CONF_ACCOUNTS: [],
            }
            return await self.async_step_account()
        return self.async_show_form(step_id="user", data_schema=HUB_SCHEMA)

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the account configuration step with protocol-specific fields."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = validate_input(user_input, self._protocol)
        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id="account",
                data_schema=self._get_account_schema(),
                errors=errors,
            )
        return await self.async_handle_data_and_route(user_input)

    async def async_step_add_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the additional accounts steps."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = validate_input(user_input, self._protocol)
        if user_input is None or errors is not None:
            return self.async_show_form(
                step_id="add_account",
                data_schema=self._get_account_schema(),
                errors=errors,
            )
        return await self.async_handle_data_and_route(user_input)

    async def async_handle_data_and_route(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
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

    def _update_data(self, user_input: dict[str, Any]) -> None:
        """Parse account input and append to data and options."""
        account = user_input[CONF_ACCOUNT]
        account_data: dict[str, Any] = {
            CONF_ACCOUNT: account,
            CONF_PING_INTERVAL: user_input[CONF_PING_INTERVAL],
        }
        if self._protocol == PROTOCOL_OH:
            panel_id_str = user_input.get(CONF_PANEL_ID, "0")
            account_data[CONF_PANEL_ID] = int(panel_id_str, 16) if panel_id_str else 0
            account_data[CONF_FORWARD_HEARTBEAT] = user_input.get(
                CONF_FORWARD_HEARTBEAT, True
            )
        else:
            account_data[CONF_ENCRYPTION_KEY] = user_input.get(CONF_ENCRYPTION_KEY)
        self._data[CONF_ACCOUNTS].append(account_data)
        self._options[CONF_ACCOUNTS].setdefault(account, deepcopy(DEFAULT_OPTIONS))
        self._options[CONF_ACCOUNTS][account][CONF_ZONES] = user_input[CONF_ZONES]


class SIAOptionsFlowHandler(OptionsFlow):
    """Handle SIA options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize SIA options flow."""
        self.options = deepcopy(dict(config_entry.options))
        self.hub: SIAHub | None = None
        self.accounts_todo: list = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the SIA options."""
        self.hub = self.hass.data[DOMAIN][self.config_entry.entry_id]
        assert self.hub is not None
        self.accounts_todo = self.hub.account_ids
        return await self.async_step_options()

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the options step for a account."""
        is_oh = self.config_entry.data.get(CONF_PROTOCOL) == PROTOCOL_OH
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = validate_zones(user_input)
        if user_input is None or errors is not None:
            account = self.accounts_todo[0]
            schema_fields: dict[vol.Optional, type] = {
                vol.Optional(
                    CONF_ZONES,
                    default=self.options[CONF_ACCOUNTS][account][CONF_ZONES],
                ): int,
            }
            if not is_oh:
                schema_fields[
                    vol.Optional(
                        CONF_IGNORE_TIMESTAMPS,
                        default=self.options[CONF_ACCOUNTS][account][
                            CONF_IGNORE_TIMESTAMPS
                        ],
                    )
                ] = bool
            return self.async_show_form(
                step_id="options",
                description_placeholders={"account": account},
                data_schema=vol.Schema(schema_fields),
                errors=errors,
                last_step=self.last_step,
            )

        account = self.accounts_todo.pop(0)
        if not is_oh:
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
