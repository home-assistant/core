"""Config flow to configure esphome component."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import logging
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
import aiohttp
import voluptuous as vol

from homeassistant.components import dhcp, zeroconf
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from . import CONF_DEVICE_NAME, CONF_NOISE_PSK
from .const import DOMAIN
from .dashboard import async_get_dashboard, async_set_dashboard_info

ERROR_REQUIRES_ENCRYPTION_KEY = "requires_encryption_key"
ERROR_INVALID_ENCRYPTION_KEY = "invalid_psk"
ESPHOME_URL = "https://esphome.io/"
_LOGGER = logging.getLogger(__name__)


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
        self._reauth_entry: ConfigEntry | None = None
        # The ESPHome name as per its config
        self._device_name: str | None = None

    async def _async_step_user_base(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            return await self._async_try_fetch_device_info()

        fields: dict[Any, type] = OrderedDict()
        fields[vol.Required(CONF_HOST, default=self._host or vol.UNDEFINED)] = str
        fields[vol.Optional(CONF_PORT, default=self._port or 6053)] = int

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={"esphome_url": ESPHOME_URL},
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
        self._reauth_entry = entry
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]
        self._password = entry.data[CONF_PASSWORD]
        self._name = entry.title
        self._device_name = entry.data.get(CONF_DEVICE_NAME)

        # Device without encryption allows fetching device info. We can then check
        # if the device is no longer using a password. If we did try with a password,
        # we know setting password to empty will allow us to authenticate.
        error = await self.fetch_device_info()
        if (
            error is None
            and self._password
            and self._device_info
            and not self._device_info.uses_password
        ):
            self._password = ""
            return await self._async_authenticate_or_add()

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization flow."""
        errors = {}

        if await self._retrieve_encryption_key_from_dashboard():
            error = await self.fetch_device_info()
            if error is None:
                return await self._async_authenticate_or_add()

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

    async def _async_try_fetch_device_info(self) -> FlowResult:
        error = await self.fetch_device_info()

        if (
            error == ERROR_REQUIRES_ENCRYPTION_KEY
            and await self._retrieve_encryption_key_from_dashboard()
        ):
            error = await self.fetch_device_info()
            # If the fetched key is invalid, unset it again.
            if error == ERROR_INVALID_ENCRYPTION_KEY:
                self._noise_psk = None
                error = ERROR_REQUIRES_ENCRYPTION_KEY

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

        self._password = ""
        return self._async_get_entry()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self._async_try_fetch_device_info()
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name}
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        mac_address: str | None = discovery_info.properties.get("mac")

        # Mac address was added in Sept 20, 2021.
        # https://github.com/esphome/esphome/pull/2303
        if mac_address is None:
            return self.async_abort(reason="mdns_missing_mac")

        # mac address is lowercase and without :, normalize it
        mac_address = format_mac(mac_address)

        # Hostname is format: livingroom.local.
        device_name = discovery_info.hostname.removesuffix(".local.")

        self._name = discovery_info.properties.get("friendly_name", device_name)
        self._device_name = device_name
        self._host = discovery_info.host
        self._port = discovery_info.port

        # Check if already configured
        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )

        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle DHCP discovery."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        # This should never happen since we only listen to DHCP requests
        # for configured devices.
        return self.async_abort(reason="already_configured")

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Handle Supervisor service discovery."""
        await async_set_dashboard_info(
            self.hass,
            discovery_info.slug,
            discovery_info.config["host"],
            discovery_info.config["port"],
        )
        return self.async_abort(reason="service_received")

    @callback
    def _async_get_entry(self) -> FlowResult:
        config_data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            # The API uses protobuf, so empty string denotes absence
            CONF_PASSWORD: self._password or "",
            CONF_NOISE_PSK: self._noise_psk or "",
            CONF_DEVICE_NAME: self._device_name,
        }
        if self._reauth_entry:
            entry = self._reauth_entry
            self.hass.config_entries.async_update_entry(
                entry, data=self._reauth_entry.data | config_data
            )
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
            return ERROR_INVALID_ENCRYPTION_KEY
        except ResolveAPIError:
            return "resolve_error"
        except APIConnectionError:
            return "connection_error"
        finally:
            await cli.disconnect(force=True)

        self._name = self._device_info.friendly_name or self._device_info.name
        self._device_name = self._device_info.name
        await self.async_set_unique_id(
            self._device_info.mac_address, raise_on_progress=False
        )
        if not self._reauth_entry:
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self._host, CONF_PORT: self._port}
            )

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

    async def _retrieve_encryption_key_from_dashboard(self) -> bool:
        """Try to retrieve the encryption key from the dashboard.

        Return boolean if a key was retrieved.
        """
        if self._device_name is None:
            return False

        if (dashboard := async_get_dashboard(self.hass)) is None:
            return False

        await dashboard.async_request_refresh()

        if not dashboard.last_update_success:
            return False

        device = dashboard.data.get(self._device_name)

        if device is None:
            return False

        try:
            noise_psk = await dashboard.api.get_encryption_key(device["configuration"])
        except aiohttp.ClientError as err:
            _LOGGER.error("Error talking to the dashboard: %s", err)
            return False

        self._noise_psk = noise_psk
        return True
