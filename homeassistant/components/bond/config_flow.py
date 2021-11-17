"""Config flow for Bond integration."""
from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from bond_api import Bond
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .utils import BondHub

_LOGGER = logging.getLogger(__name__)


USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_ACCESS_TOKEN): str}
)
DISCOVERY_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
TOKEN_SCHEMA = vol.Schema({})


async def async_get_token(hass: HomeAssistant, host: str) -> str | None:
    """Try to fetch the token from the bond device."""
    bond = Bond(host, "", session=async_get_clientsession(hass))
    try:
        response: dict[str, str] = await bond.token()
    except ClientConnectionError:
        return None
    return response.get("token")


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> tuple[str, str]:
    """Validate the user input allows us to connect."""

    bond = Bond(
        data[CONF_HOST], data[CONF_ACCESS_TOKEN], session=async_get_clientsession(hass)
    )
    try:
        hub = BondHub(bond)
        await hub.setup(max_devices=1)
    except ClientConnectionError as error:
        raise InputValidationError("cannot_connect") from error
    except ClientResponseError as error:
        if error.status == HTTPStatus.UNAUTHORIZED:
            raise InputValidationError("invalid_auth") from error
        raise InputValidationError("unknown") from error
    except Exception as error:
        _LOGGER.exception("Unexpected exception")
        raise InputValidationError("unknown") from error

    # Return unique ID from the hub to be stored in the config entry.
    if not hub.bond_id:
        raise InputValidationError("old_firmware")

    return hub.bond_id, hub.name


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bond."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered: dict[str, str] = {}

    async def _async_try_automatic_configure(self) -> None:
        """Try to auto configure the device.

        Failure is acceptable here since the device may have been
        online longer then the allowed setup period, and we will
        instead ask them to manually enter the token.
        """
        host = self._discovered[CONF_HOST]
        if not (token := await async_get_token(self.hass, host)):
            return

        self._discovered[CONF_ACCESS_TOKEN] = token
        _, hub_name = await _validate_input(self.hass, self._discovered)
        self._discovered[CONF_NAME] = hub_name

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        name: str = discovery_info[zeroconf.ATTR_NAME]
        host: str = discovery_info[zeroconf.ATTR_HOST]
        bond_id = name.partition(".")[0]
        await self.async_set_unique_id(bond_id)
        for entry in self._async_current_entries():
            if entry.unique_id != bond_id:
                continue
            updates = {CONF_HOST: host}
            if entry.state == ConfigEntryState.SETUP_ERROR and (
                token := await async_get_token(self.hass, host)
            ):
                updates[CONF_ACCESS_TOKEN] = token
            new_data = {**entry.data, **updates}
            if new_data != dict(entry.data):
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **updates}
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
            raise AbortFlow("already_configured")

        self._discovered = {CONF_HOST: host, CONF_NAME: bond_id}
        await self._async_try_automatic_configure()

        self.context.update(
            {
                "title_placeholders": {
                    CONF_HOST: self._discovered[CONF_HOST],
                    CONF_NAME: self._discovered[CONF_NAME],
                }
            }
        )

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle confirmation flow for discovered bond hub."""
        errors = {}
        if user_input is not None:
            if CONF_ACCESS_TOKEN in self._discovered:
                return self.async_create_entry(
                    title=self._discovered[CONF_NAME],
                    data={
                        CONF_ACCESS_TOKEN: self._discovered[CONF_ACCESS_TOKEN],
                        CONF_HOST: self._discovered[CONF_HOST],
                    },
                )

            data = {
                CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                CONF_HOST: self._discovered[CONF_HOST],
            }
            try:
                _, hub_name = await _validate_input(self.hass, data)
            except InputValidationError as error:
                errors["base"] = error.base
            else:
                return self.async_create_entry(
                    title=hub_name,
                    data=data,
                )

        if CONF_ACCESS_TOKEN in self._discovered:
            data_schema = TOKEN_SCHEMA
        else:
            data_schema = DISCOVERY_SCHEMA

        return self.async_show_form(
            step_id="confirm",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=self._discovered,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                bond_id, hub_name = await _validate_input(self.hass, user_input)
            except InputValidationError as error:
                errors["base"] = error.base
            else:
                await self.async_set_unique_id(bond_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=hub_name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )


class InputValidationError(exceptions.HomeAssistantError):
    """Error to indicate we cannot proceed due to invalid input."""

    def __init__(self, base: str) -> None:
        """Initialize with error base."""
        super().__init__()
        self.base = base
