"""Config flow to configure esphome component."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from typing import Any

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    DeviceInfo,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    RequiresEncryptionAPIError,
    ResolveAPIError,
)
import voluptuous as vol

from homeassistant.components import dhcp, zeroconf
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import CONF_NOISE_PSK, DOMAIN, DomainData

ERROR_REQUIRES_ENCRYPTION_KEY = "requires_encryption_key"


class EsphomeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a esphome config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._port: int | None = None
        self._password: str | None = None
        self._noise_psk: str | None = None
        self._device_info: DeviceInfo | None = None

    async def _async_step_user_base(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> FlowResult:
        if user_input is not None:
            return await self._async_try_fetch_device_info(user_input)

        fields: dict[Any, type] = OrderedDict()
        fields[vol.Required(CONF_HOST, default=self._host or vol.UNDEFINED)] = str
        fields[vol.Optional(CONF_PORT, default=self._port or 6053)] = int

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self._async_step_user_base(user_input=user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle a flow initialized by a reauth event."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]
        self._password = entry.data[CONF_PASSWORD]
        self._noise_psk = entry.data.get(CONF_NOISE_PSK)
        self._name = entry.title
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization flow."""
        errors = {}

        if user_input is not None:
            self._noise_psk = user_input[CONF_NOISE_PSK]
            error = await self.fetch_device_info()
            if error is None:
                return await self._async_authenticate_or_add()
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_NOISE_PSK): str}),
            errors=errors,
            description_placeholders={"name": self._name},
        )

    @property
    def _name(self) -> str | None:
        return self.context.get(CONF_NAME)

    @_name.setter
    def _name(self, value: str) -> None:
        self.context[CONF_NAME] = value
        self.context["title_placeholders"] = {"name": self._name}

    def _set_user_input(self, user_input: dict[str, Any] | None) -> None:
        if user_input is None:
            return
        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]

    async def _async_try_fetch_device_info(
        self, user_input: dict[str, Any] | None
    ) -> FlowResult:
        self._set_user_input(user_input)
        error = await self.fetch_device_info()
        if error == ERROR_REQUIRES_ENCRYPTION_KEY:
            return await self.async_step_encryption_key()
        if error is not None:
            return await self._async_step_user_base(error=error)
        return await self._async_authenticate_or_add()

    async def _async_authenticate_or_add(self) -> FlowResult:
        # Only show authentication step if device uses password
        assert self._device_info is not None
        if self._device_info.uses_password:
            return await self.async_step_authenticate()

        return self._async_get_entry()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self._async_try_fetch_device_info(None)
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name}
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        # Hostname is format: livingroom.local.
        local_name = discovery_info.hostname[:-1]
        node_name = local_name[: -len(".local")]
        address = discovery_info.properties.get("address", local_name)

        # Check if already configured
        await self.async_set_unique_id(node_name)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        for entry in self._async_current_entries():
            already_configured = False

            if CONF_HOST in entry.data and entry.data[CONF_HOST] in (
                address,
                discovery_info.host,
            ):
                # Is this address or IP address already configured?
                already_configured = True
            elif DomainData.get(self.hass).is_entry_loaded(entry):
                # Does a config entry with this name already exist?
                data = DomainData.get(self.hass).get_entry_data(entry)

                # Node names are unique in the network
                if data.device_info is not None:
                    already_configured = data.device_info.name == node_name

            if already_configured:
                # Backwards compat, we update old entries
                if not entry.unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_HOST: discovery_info.host,
                        },
                        unique_id=node_name,
                    )

                return self.async_abort(reason="already_configured")

        self._host = discovery_info.host
        self._port = discovery_info.port
        self._name = node_name

        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle DHCP discovery."""
        node_name = discovery_info.hostname

        await self.async_set_unique_id(node_name)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        for entry in self._async_current_entries():
            found = False

            if CONF_HOST in entry.data and entry.data[CONF_HOST] in (
                discovery_info.ip,
                f"{node_name}.local",
            ):
                # Is this address or IP address already configured?
                found = True
            elif DomainData.get(self.hass).is_entry_loaded(entry):
                # Does a config entry with this name already exist?
                data = DomainData.get(self.hass).get_entry_data(entry)

                # Node names are unique in the network
                if data.device_info is not None:
                    found = data.device_info.name == node_name

            if found:
                # Backwards compat, we update old entries
                if not entry.unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_HOST: discovery_info.ip,
                        },
                        unique_id=node_name,
                    )
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )

                break

        return self.async_abort(reason="already_configured")

    @callback
    def _async_get_entry(self) -> FlowResult:
        config_data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            # The API uses protobuf, so empty string denotes absence
            CONF_PASSWORD: self._password or "",
            CONF_NOISE_PSK: self._noise_psk or "",
        }
        if "entry_id" in self.context:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            assert entry is not None
            self.hass.config_entries.async_update_entry(entry, data=config_data)
            # Reload the config entry to notify of updated config
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        assert self._name is not None
        return self.async_create_entry(
            title=self._name,
            data=config_data,
        )

    async def async_step_encryption_key(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle getting psk for transport encryption."""
        errors = {}
        if user_input is not None:
            self._noise_psk = user_input[CONF_NOISE_PSK]
            error = await self.fetch_device_info()
            if error is None:
                return await self._async_authenticate_or_add()
            errors["base"] = error

        return self.async_show_form(
            step_id="encryption_key",
            data_schema=vol.Schema({vol.Required(CONF_NOISE_PSK): str}),
            errors=errors,
            description_placeholders={"name": self._name},
        )

    async def async_step_authenticate(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> FlowResult:
        """Handle getting password for authentication."""
        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            error = await self.try_login()
            if error:
                return await self.async_step_authenticate(error=error)
            return self._async_get_entry()

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="authenticate",
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"name": self._name},
            errors=errors,
        )

    async def fetch_device_info(self) -> str | None:
        """Fetch device info from API and return any errors."""
        zeroconf_instance = await zeroconf.async_get_instance(self.hass)
        assert self._host is not None
        assert self._port is not None
        cli = APIClient(
            self._host,
            self._port,
            "",
            zeroconf_instance=zeroconf_instance,
            noise_psk=self._noise_psk,
        )

        try:
            await cli.connect()
            self._device_info = await cli.device_info()
        except RequiresEncryptionAPIError:
            return ERROR_REQUIRES_ENCRYPTION_KEY
        except InvalidEncryptionKeyAPIError:
            return "invalid_psk"
        except ResolveAPIError:
            return "resolve_error"
        except APIConnectionError:
            return "connection_error"
        finally:
            await cli.disconnect(force=True)

        self._name = self._device_info.name

        return None

    async def try_login(self) -> str | None:
        """Try logging in to device and return any errors."""
        zeroconf_instance = await zeroconf.async_get_instance(self.hass)
        assert self._host is not None
        assert self._port is not None
        cli = APIClient(
            self._host,
            self._port,
            self._password,
            zeroconf_instance=zeroconf_instance,
            noise_psk=self._noise_psk,
        )

        try:
            await cli.connect(login=True)
        except InvalidAuthAPIError:
            return "invalid_auth"
        except APIConnectionError:
            return "connection_error"
        finally:
            await cli.disconnect(force=True)

        return None
