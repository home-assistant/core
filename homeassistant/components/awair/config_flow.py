"""Config flow for Awair."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from python_awair import Awair, AwairLocal
from python_awair.exceptions import AuthError, AwairError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOSTS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER


class AwairFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Awair."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        return self.async_show_menu(
            step_id="user",
            menu_options=["cloud", "local"],
            description_placeholders={"cloud": "Cloud API", "local": "Local API"},
        )

    async def async_step_cloud(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle collecting and verifying Awair Cloud API credentials."""

        errors = {}

        if user_input is not None:
            user, error = await self._check_cloud_connection(
                user_input[CONF_ACCESS_TOKEN]
            )

            if user is not None:
                await self.async_set_unique_id(user.email)
                self._abort_if_unique_id_configured()

                title = f"{user.email} ({user.user_id})"
                return self.async_create_entry(title=title, data=user_input)

            if error != "invalid_access_token":
                return self.async_abort(reason=error)

            errors = {CONF_ACCESS_TOKEN: "invalid_access_token"}

        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema({vol.Optional(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )

    async def async_step_local(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle collecting and verifying Awair Local API hosts."""

        errors = {}

        if user_input is not None:
            devices, error = await self._check_local_connection(user_input[CONF_HOSTS])

            if devices is not None:
                await self.async_set_unique_id(user_input[CONF_HOSTS])
                self._abort_if_unique_id_configured()

                title = f"Awair Local Sensors: {user_input[CONF_HOSTS]}"
                return self.async_create_entry(title=title, data=user_input)

            if error != "auth":
                return self.async_abort(reason=error)

            errors = {CONF_HOSTS: "auth"}

        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema({vol.Required(CONF_HOSTS): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-auth if token invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = {}

        if user_input is not None:
            access_token = user_input[CONF_ACCESS_TOKEN]
            _, error = await self._check_cloud_connection(access_token)

            if error is None:
                entry = await self.async_set_unique_id(self.unique_id)
                assert entry
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                return self.async_abort(reason="reauth_successful")

            if error != "invalid_access_token":
                return self.async_abort(reason=error)

            errors = {CONF_ACCESS_TOKEN: error}

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )

    async def _check_local_connection(self, device_addrs_str: str):
        """Check the access token is valid."""
        device_addrs = [addr.strip() for addr in device_addrs_str.split(",")]
        session = async_get_clientsession(self.hass)
        awair = AwairLocal(session=session, device_addrs=device_addrs)

        try:
            devices = await awair.devices()
            if not devices:
                return (None, "no_devices")

            if len(devices) != len(device_addrs):
                return (None, "not enough devices")

            return (devices[0], None)

        except AwairError as err:
            LOGGER.error("Unexpected API error: %s", err)
            return (None, "unknown")

    async def _check_cloud_connection(self, access_token: str):
        """Check the access token is valid."""
        session = async_get_clientsession(self.hass)
        awair = Awair(access_token=access_token, session=session)

        try:
            user = await awair.user()
            devices = await user.devices()
            if not devices:
                return (None, "no_devices_found")

            return (user, None)

        except AuthError:
            return (None, "invalid_access_token")
        except AwairError as err:
            LOGGER.error("Unexpected API error: %s", err)
            return (None, "unknown")
