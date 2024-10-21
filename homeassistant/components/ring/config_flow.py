"""Config flow for Ring integration."""

from collections.abc import Mapping
import logging
from typing import Any
import uuid

from ring_doorbell import Auth, AuthenticationError, Requires2FAError
import voluptuous as vol

from homeassistant.components import dhcp
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.device_registry as dr

from . import get_auth_user_agent
from .const import CONF_2FA, CONF_CONFIG_ENTRY_MINOR_VERSION, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})

UNKNOWN_RING_ACCOUNT = "unknown_ring_account"


async def validate_input(
    hass: HomeAssistant, hardware_id: str, data: dict[str, str]
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    user_agent = get_auth_user_agent()
    auth = Auth(
        user_agent,
        http_client_session=async_get_clientsession(hass),
        hardware_id=hardware_id,
    )

    try:
        token = await auth.async_fetch_token(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data.get(CONF_2FA),
        )
    except Requires2FAError as err:
        raise Require2FA from err
    except AuthenticationError as err:
        raise InvalidAuth from err

    return token


class RingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring."""

    VERSION = 1
    MINOR_VERSION = CONF_CONFIG_ENTRY_MINOR_VERSION

    user_pass: dict[str, Any] = {}
    hardware_id: str | None = None

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        # Ring has a single config entry per cloud username rather than per device
        # so we check whether that device is already configured.
        # If the device is not configured there's either no ring config entry
        # yet or the device is registered to a different account
        await self.async_set_unique_id(UNKNOWN_RING_ACCOUNT)
        self._abort_if_unique_id_configured()
        if self.hass.config_entries.async_has_entries(DOMAIN):
            device_registry = dr.async_get(self.hass)
            if device_registry.async_get_device(
                identifiers={(DOMAIN, discovery_info.macaddress)}
            ):
                return self.async_abort(reason="already_configured")

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            if not self.hardware_id:
                self.hardware_id = str(uuid.uuid4())
            try:
                token = await validate_input(self.hass, self.hardware_id, user_input)
            except Require2FA:
                self.user_pass = user_input

                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_DEVICE_ID: self.hardware_id,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle 2fa step."""
        if user_input:
            if self.source == SOURCE_REAUTH:
                return await self.async_step_reauth_confirm(
                    {**self.user_pass, **user_input}
                )

            if self.source == SOURCE_RECONFIGURE:
                return await self.async_step_reconfigure(
                    {**self.user_pass, **user_input}
                )

            return await self.async_step_user({**self.user_pass, **user_input})

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema({vol.Required(CONF_2FA): str}),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input:
            user_input[CONF_USERNAME] = reauth_entry.data[CONF_USERNAME]
            # Reauth will use the same hardware id and re-authorise an existing
            # authorised device.
            if not self.hardware_id:
                self.hardware_id = reauth_entry.data[CONF_DEVICE_ID]
                assert self.hardware_id
            try:
                token = await validate_input(self.hass, self.hardware_id, user_input)
            except Require2FA:
                self.user_pass = user_input
                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_TOKEN: token,
                    CONF_DEVICE_ID: self.hardware_id,
                }
                return self.async_update_reload_and_abort(reauth_entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                CONF_NAME: reauth_entry.data[CONF_USERNAME],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Trigger a reconfiguration flow."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        username = reconfigure_entry.data[CONF_USERNAME]
        await self.async_set_unique_id(username)
        if user_input:
            user_input[CONF_USERNAME] = username
            # Reconfigure will generate a new hardware id and create a new
            # authorised device at ring.com.
            if not self.hardware_id:
                self.hardware_id = str(uuid.uuid4())
            try:
                assert self.hardware_id
                token = await validate_input(self.hass, self.hardware_id, user_input)
            except Require2FA:
                self.user_pass = user_input
                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = {
                    CONF_USERNAME: username,
                    CONF_TOKEN: token,
                    CONF_DEVICE_ID: self.hardware_id,
                }
                return self.async_update_reload_and_abort(reconfigure_entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_RECONFIGURE_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                CONF_USERNAME: username,
            },
        )


class Require2FA(HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
