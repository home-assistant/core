"""Config flow for openevse integration."""
from __future__ import annotations

import logging

from openevsewifi import Charger, InvalidAuthentication
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components import zeroconf
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_http(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect over HTTP."""

    host_with_port = f"{data[CONF_HOST]}:{data[CONF_PORT]}"
    charger = Charger(
        host=host_with_port,
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
    )

    _LOGGER.debug("Connecting to %s for initial status check", host_with_port)
    try:
        status = await hass.async_add_executor_job(Charger.status.fget, charger)
        _LOGGER.info("Connected to charger with status '%s'", status)
    except InvalidAuthentication as error:
        raise InvalidAuth from error


class OpenEvseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for openevse."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._port: int | None = DEFAULT_PORT
        self._name: str | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._discovery_name: str | None = None

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        self._name = discovery_info.hostname.removesuffix(".local.")
        if not (uid := discovery_info.properties.get("id")):
            return self.async_abort(reason="no_id")

        self._discovery_name = discovery_info.name

        await self.async_set_unique_id(uid)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_NAME: self._name,
            }
        )

        self.context.update({"title_placeholders": {CONF_NAME: self._name}})

        try:
            await validate_http(self.hass, self._get_data())
        except InvalidAuth:
            return await self.async_step_credentials()
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={"name": self._name},
            )

        return self._create_entry()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]

            try:
                await validate_http(self.hass, self._get_data())
            except InvalidAuth:
                return await self.async_step_credentials()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self._create_entry()

        return self._show_user_form(errors)

    async def async_step_credentials(self, user_input=None):
        """Handle username and password input."""
        errors = {}

        if user_input is not None:
            self._username = user_input.get(CONF_USERNAME)
            self._password = user_input.get(CONF_PASSWORD)

            try:
                await validate_http(self.hass, self._get_data())
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self._create_entry()

        return self._show_credentials_form(errors)

    async def async_step_import(self, data):
        """Handle import from YAML."""
        reason = None
        try:
            await validate_http(self.hass, data)
        except InvalidAuth:
            _LOGGER.exception("Invalid credentials")
            reason = "invalid_auth"
        except CannotConnect:
            _LOGGER.exception("Cannot connect")
            reason = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            reason = "unknown"
        else:
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_abort(reason=reason)

    @callback
    def _show_credentials_form(self, errors=None):
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USERNAME, description={"suggested_value": self._username}
                ): str,
                vol.Optional(
                    CONF_PASSWORD, description={"suggested_value": self._password}
                ): str,
            }
        )

        return self.async_show_form(
            step_id="credentials", data_schema=schema, errors=errors or {}
        )

    @callback
    def _show_user_form(self, errors=None):
        default_port = self._port or DEFAULT_PORT
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_PORT, default=default_port): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors or {}
        )

    @callback
    def _create_entry(self):
        return self.async_create_entry(
            title=self._name or self._host,
            data=self._get_data(),
        )

    @callback
    def _get_data(self):
        data = {
            CONF_NAME: self._name,
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
        }

        return data


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
