"""Config flow for the my-PV integration."""

from collections.abc import Mapping
import logging
from typing import Any, Final

from my_pv import MyPVCloudDevice, MyPVDevice, MyPVLocalDevice
from my_pv.exceptions import MyPVAuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_SERIAL_NUMBER, CONF_TYPE_CLOUD, CONF_TYPE_LOCAL, DOMAIN

_LOGGER: Final = logging.getLogger(__name__)

_VALIDATE_SERIAL_NUMBER = cv.matches_regex(r"^.{16}$")
_VALIDATE_CLOUD_API_TOKEN = cv.matches_regex(r"^my.{46}PV$")


class MyPVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for my-PV."""

    _host: str
    _discovered_device: MyPVDevice | None = None
    _password_needed: bool = False

    _reauth_entry: ConfigEntry | None = None

    LOCAL_HOST_SCHEMA: Final = vol.Schema(
        {
            vol.Required(CONF_HOST): TextSelector(),
        }
    )
    LOCAL_AUTH_SCHEMA: Final = vol.Schema(
        {
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }
    )
    CLOUD_SCHEMA: Final = vol.Schema(
        {
            vol.Required(CONF_SERIAL_NUMBER): TextSelector(),
            vol.Required(CONF_TOKEN): TextSelector(),
        }
    )
    CLOUD_REAUTH_SCHEMA: Final = vol.Schema(
        {
            vol.Required(CONF_TOKEN): TextSelector(),
        }
    )

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
        if (
            self._discovered_device
            and user_input is not None
            and not self._password_needed
        ):
            await self.async_set_unique_id(self._discovered_device.serial_number)
            self._abort_if_unique_id_configured()

            title = f"my-PV {self._discovered_device.model}"
            data = {
                CONF_TYPE: CONF_TYPE_LOCAL,
                CONF_HOST: self._host,
            }
            return self.async_create_entry(title=title, data=data)

        errors: dict[str, str] = {}

        password = None
        if user_input:
            password = user_input.get(CONF_PASSWORD)

        password_needed = False
        if password:
            password_needed = True

        # Check if we can connect to the device
        device = await MyPVLocalDevice(self._host, password)
        try:
            if not await device.connect():
                return self.async_abort(reason="cannot_connect")
        except MyPVAuthenticationError:
            if user_input:
                errors[CONF_PASSWORD] = "invalid_password"
            password_needed = True
        await device.disconnect()

        if user_input is None:
            await self.async_set_unique_id(device.serial_number)
            # Update host ip address when device is already configured and abort.
            self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

            _LOGGER.debug("my-PV on %s is not yet configured", self._host)

            self._discovered_device = device
            self._password_needed = password_needed

        self.context.update(
            {
                "title_placeholders": {
                    "name": f"my-PV {device.model}",
                }
            }
        )

        if password_needed:
            return await self.async_step_local_auth()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        # pylint: disable=unused-argument
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[
                "setup_local",
                "setup_cloud",
            ],
        )

    async def async_step_setup_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the local setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="setup_local",
                data_schema=self.LOCAL_HOST_SCHEMA,
            )

        errors: dict[str, str] = {}

        host = user_input[CONF_HOST]

        # Check if we can connect to the device
        device = await MyPVLocalDevice(host)
        try:
            if not await device.connect():
                errors[CONF_BASE] = "cannot_connect"
        except MyPVAuthenticationError:
            self._host = host
            return await self.async_step_local_auth()
        finally:
            await device.disconnect()

        if errors:
            # Combine user input with schema.
            data_schema = self.add_suggested_values_to_schema(
                self.LOCAL_HOST_SCHEMA, user_input
            )
            return self.async_show_form(
                step_id="setup_local",
                data_schema=data_schema,
                errors=errors,
            )

        await self.async_set_unique_id(device.serial_number)
        self._abort_if_unique_id_configured()

        title = f"my-PV {device.model}"
        data = {
            CONF_TYPE: CONF_TYPE_LOCAL,
            CONF_HOST: host,
        }
        return self.async_create_entry(title=title, data=data)

    async def async_step_local_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle local password authentication."""
        if user_input is None:
            return self.async_show_form(
                step_id="local_auth",
                data_schema=self.LOCAL_AUTH_SCHEMA,
            )

        errors: dict[str, str] = {}

        if self._reauth_entry:
            host = self._reauth_entry.data[CONF_HOST]
        elif self._host:
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

        # If reauthenticating only the existing configuration needs to be updated with the
        # new password.
        if self._reauth_entry is not None:
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data_updates={
                    CONF_PASSWORD: password,
                },
            )

        if errors:
            # Combine user input with schema.
            data_schema = self.add_suggested_values_to_schema(
                self.LOCAL_AUTH_SCHEMA, user_input
            )
            return self.async_show_form(
                step_id="setup_local",
                data_schema=data_schema,
                errors=errors,
            )

        await self.async_set_unique_id(device.serial_number)
        self._abort_if_unique_id_configured()

        title = f"my-PV {device.model}"
        data = {
            CONF_TYPE: CONF_TYPE_LOCAL,
            CONF_HOST: host,
            CONF_PASSWORD: password,
        }
        return self.async_create_entry(title=title, data=data)

    async def async_step_setup_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the cloud setup."""
        if user_input is None and self._reauth_entry is not None:
            return self.async_show_form(
                step_id="setup_cloud",
                data_schema=self.CLOUD_REAUTH_SCHEMA,
            )
        if user_input is None:
            return self.async_show_form(
                step_id="setup_cloud",
                data_schema=self.CLOUD_SCHEMA,
            )

        errors: dict[str, str] = {}

        if self._reauth_entry:
            serial_number = self._reauth_entry.data[CONF_SERIAL_NUMBER]
        else:
            serial_number = user_input[CONF_SERIAL_NUMBER]

            # Validate serial number.
            try:
                _VALIDATE_SERIAL_NUMBER(serial_number)
            except vol.Invalid:
                errors[CONF_SERIAL_NUMBER] = "invalid_serial_number"

        api_token = user_input[CONF_TOKEN]

        # Validate API token.
        try:
            _VALIDATE_CLOUD_API_TOKEN(api_token)
        except vol.Invalid:
            errors[CONF_TOKEN] = "invalid_cloud_api_token"

        # Test if we can connect to the cloud.
        device = await MyPVCloudDevice(serial_number, api_token)
        try:
            if not await device.connect():
                errors[CONF_BASE] = "cannot_connect"
            await device.disconnect()
        except MyPVAuthenticationError:
            errors[CONF_TOKEN] = "invalid_cloud_api_token"

        if errors:
            # Combine user input with schema.
            if self._reauth_entry:
                data_schema = self.add_suggested_values_to_schema(
                    self.CLOUD_REAUTH_SCHEMA, user_input
                )
            else:
                data_schema = self.add_suggested_values_to_schema(
                    self.CLOUD_SCHEMA, user_input
                )
            return self.async_show_form(
                step_id="setup_cloud",
                data_schema=data_schema,
                errors=errors,
            )

        # If reauthenticating only the existing configuration needs to be updated with the
        # new API token.
        if self._reauth_entry is not None:
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data_updates={
                    CONF_TOKEN: api_token,
                },
            )

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        title = f"my-PV {device.model}"
        data = {
            CONF_TYPE: CONF_TYPE_CLOUD,
            CONF_SERIAL_NUMBER: serial_number,
            CONF_TOKEN: api_token,
        }
        return self.async_create_entry(title=title, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        # pylint: disable=unused-argument
        """Perform reauth upon an authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        if entry_data[CONF_TYPE] == CONF_TYPE_LOCAL:
            _LOGGER.debug("Reauthentication needed for my-PV Cloud")
            return await self.async_step_local_auth()

        if entry_data[CONF_TYPE] == CONF_TYPE_CLOUD:
            _LOGGER.debug("Reauthentication needed for my-PV Cloud")
            return await self.async_step_setup_cloud()

        return self.async_abort(
            reason="config_type_not_supported",
            description_placeholders={"config_type": entry_data[CONF_TYPE]},
        )
