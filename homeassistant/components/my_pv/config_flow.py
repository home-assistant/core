"""Config flow for the my-PV integration."""

import logging
from typing import Any, Final

from my_pv import MyPVLocalDevice
from my_pv.exceptions import MyPVAuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_LOGGER: Final = logging.getLogger(__name__)


HOST_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
    }
)
AUTH_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class MyPVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for my-PV."""

    _host: str
    _device_model: str

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug(
            "Zeroconf discovery detected my-PV on %s",
            discovery_info.ip_address,
        )

        self._host = str(discovery_info.ip_address)

        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        _LOGGER.debug(
            "DHCP discovery detected my-PV on %s (%s)",
            discovery_info.ip,
            format_mac(discovery_info.macaddress),
        )

        self._host = discovery_info.ip

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirmation."""
        password_needed = False

        # Check if we can connect to the device
        device = await MyPVLocalDevice(self._host)
        try:
            if not await device.connect():
                return self.async_abort(reason="cannot_connect")
        except MyPVAuthenticationError:
            password_needed = True
        finally:
            await device.disconnect()

        await self.async_set_unique_id(device.serial_number)
        # Update host ip address when device is already configured and abort.
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        if password_needed:
            self._device_model = device.model
            return await self.async_step_discovery_auth()

        title = f"my-PV {device.model}"

        if user_input is not None:
            data = {
                CONF_HOST: self._host,
            }
            return self.async_create_entry(title=title, data=data)

        _LOGGER.debug("my-PV on %s is not yet configured", self._host)
        self.context.update(
            {
                "title_placeholders": {
                    "name": title,
                }
            }
        )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_discovery_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery password authentication."""
        errors: dict[str, str] = {}
        data_schema = AUTH_SCHEMA

        if user_input is not None:
            host = self._host
            password = user_input.get(CONF_PASSWORD)

            # Check if we can connect to the device
            device = await MyPVLocalDevice(host, password)
            try:
                if not await device.connect():
                    errors[CONF_BASE] = "cannot_connect"
            except MyPVAuthenticationError:
                errors[CONF_PASSWORD] = "invalid_password"
            finally:
                await device.disconnect()

            if not errors:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()

                title = f"my-PV {device.model}"
                data = {
                    CONF_HOST: host,
                    CONF_PASSWORD: password,
                }
                return self.async_create_entry(title=title, data=data)

            # Combine user input with schema.
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)

        self.context.update(
            {
                "title_placeholders": {
                    "name": f"my-PV {self._device_model}",
                }
            }
        )

        return self.async_show_form(
            step_id="discovery_auth",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the local setup."""
        errors: dict[str, str] = {}
        data_schema = HOST_SCHEMA

        if user_input is not None:
            host = user_input[CONF_HOST]
            password_needed = False

            # Check if we can connect to the device
            device = await MyPVLocalDevice(host)
            try:
                if not await device.connect():
                    errors[CONF_BASE] = "cannot_connect"
            except MyPVAuthenticationError:
                password_needed = True
            finally:
                await device.disconnect()

            if not errors and password_needed:
                self._host = host
                self._device_model = device.model
                return await self.async_step_auth()

            if not errors:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()

                title = f"my-PV {device.model}"
                data = {
                    CONF_HOST: host,
                }
                return self.async_create_entry(title=title, data=data)

            # Combine user input with schema.
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle password authentication."""
        errors: dict[str, str] = {}
        data_schema = AUTH_SCHEMA

        if user_input is not None:
            host = self._host
            password = user_input.get(CONF_PASSWORD)

            # Check if we can connect to the device
            device = await MyPVLocalDevice(host, password)
            try:
                if not await device.connect():
                    errors[CONF_BASE] = "cannot_connect"
            except MyPVAuthenticationError:
                errors[CONF_PASSWORD] = "invalid_password"
            finally:
                await device.disconnect()

            if not errors:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()

                title = f"my-PV {device.model}"
                data = {
                    CONF_HOST: host,
                    CONF_PASSWORD: password,
                }
                return self.async_create_entry(title=title, data=data)

            # Combine user input with schema.
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)

        self.context.update(
            {
                "title_placeholders": {
                    "name": f"my-PV {self._device_model}",
                }
            }
        )

        return self.async_show_form(
            step_id="auth",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=self.context["title_placeholders"],
        )
