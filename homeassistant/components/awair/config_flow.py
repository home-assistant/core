"""Config flow for Awair."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from python_awair import Awair, AwairLocal, AwairLocalDevice
from python_awair.exceptions import AuthError, AwairError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER


class AwairFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Awair."""

    VERSION = 1

    _device: AwairLocalDevice

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        host = discovery_info.host
        LOGGER.debug("Discovered device: %s", host)

        self._device, _ = await self._check_local_connection(host)

        if self._device is not None:
            await self.async_set_unique_id(self._device.mac_address)
            self._abort_if_unique_id_configured(error="already_configured_device")
            self.context.update(
                {
                    "title_placeholders": {
                        "model": self._device.model,
                        "device_id": self._device.device_id,
                    }
                }
            )
        else:
            return self.async_abort(reason="unreachable")
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            title = f"{self._device.model} ({self._device.device_id})"
            return self.async_create_entry(
                title=title,
                data={CONF_HOST: self._device.device_addr},
            )

        self._set_confirm_only()
        placeholders = {
            "model": self._device.model,
            "device_id": self._device.device_id,
        }
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=placeholders,
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        return self.async_show_menu(step_id="user", menu_options=["local", "cloud"])

    async def async_step_cloud(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle collecting and verifying Awair Cloud API credentials."""

        errors = {}

        if user_input is not None:
            user, error = await self._check_cloud_connection(
                user_input[CONF_ACCESS_TOKEN]
            )

            if user is not None:
                await self.async_set_unique_id(user.email)
                self._abort_if_unique_id_configured(error="already_configured_account")

                title = user.email
                return self.async_create_entry(title=title, data=user_input)

            if error != "invalid_access_token":
                return self.async_abort(reason=error)

            errors = {CONF_ACCESS_TOKEN: "invalid_access_token"}

        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema({vol.Optional(CONF_ACCESS_TOKEN): str}),
            description_placeholders={
                "url": "https://developer.getawair.com/onboard/login"
            },
            errors=errors,
        )

    async def async_step_local(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle collecting and verifying Awair Local API hosts."""

        errors = {}

        if user_input is not None:
            self._device, error = await self._check_local_connection(
                user_input[CONF_HOST]
            )

            if self._device is not None:
                await self.async_set_unique_id(self._device.mac_address)
                self._abort_if_unique_id_configured(error="already_configured_device")
                title = f"{self._device.model} ({self._device.device_id})"
                return self.async_create_entry(title=title, data=user_input)

            if error is not None:
                errors = {CONF_HOST: error}

        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            description_placeholders={
                "url": "https://support.getawair.com/hc/en-us/articles/360049221014-Awair-Element-Local-API-Feature"
            },
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

    async def _check_local_connection(self, device_address: str):
        """Check the access token is valid."""
        session = async_get_clientsession(self.hass)
        awair = AwairLocal(session=session, device_addrs=[device_address])

        try:
            devices = await awair.devices()
            return (devices[0], None)

        except ClientConnectorError as err:
            LOGGER.error("Unable to connect error: %s", err)
            return (None, "unreachable")

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
