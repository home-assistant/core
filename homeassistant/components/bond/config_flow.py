"""Config flow for Bond integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError
from bond_api import Bond
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    CONF_NAME,
    HTTP_UNAUTHORIZED,
)
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN
from .utils import BondHub

_LOGGER = logging.getLogger(__name__)


USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_ACCESS_TOKEN): str}
)
DISCOVERY_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
TOKEN_SCHEMA = vol.Schema({})


async def _validate_input(data: dict[str, Any]) -> tuple[str, str]:
    """Validate the user input allows us to connect."""

    bond = Bond(data[CONF_HOST], data[CONF_ACCESS_TOKEN])
    try:
        hub = BondHub(bond)
        await hub.setup(max_devices=1)
    except ClientConnectionError as error:
        raise InputValidationError("cannot_connect") from error
    except ClientResponseError as error:
        if error.status == HTTP_UNAUTHORIZED:
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
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered: dict[str, str] = {}

    async def _async_try_automatic_configure(self) -> None:
        """Try to auto configure the device.

        Failure is acceptable here since the device may have been
        online longer then the allowed setup period, and we will
        instead ask them to manually enter the token.
        """
        bond = Bond(self._discovered[CONF_HOST], "")
        try:
            response = await bond.token()
        except ClientConnectionError:
            return

        token = response.get("token")
        if token is None:
            return

        self._discovered[CONF_ACCESS_TOKEN] = token
        _, hub_name = await _validate_input(self._discovered)
        self._discovered[CONF_NAME] = hub_name

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType) -> dict[str, Any]:  # type: ignore
        """Handle a flow initialized by zeroconf discovery."""
        name: str = discovery_info[CONF_NAME]
        host: str = discovery_info[CONF_HOST]
        bond_id = name.partition(".")[0]
        await self.async_set_unique_id(bond_id)
        self._abort_if_unique_id_configured({CONF_HOST: host})

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
    ) -> dict[str, Any]:
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
                _, hub_name = await _validate_input(data)
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
    ) -> dict[str, Any]:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                bond_id, hub_name = await _validate_input(user_input)
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

    def __init__(self, base: str):
        """Initialize with error base."""
        super().__init__()
        self.base = base
