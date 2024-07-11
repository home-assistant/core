"""Config flow to configure esphome component."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import json
import logging
from typing import Any, cast

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
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.util.json import json_loads_object

from .const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_DEVICE_NAME,
    CONF_NOISE_PSK,
    DEFAULT_ALLOW_SERVICE_CALLS,
    DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
    DOMAIN,
)
from .dashboard import async_get_or_create_dashboard_manager, async_set_dashboard_info

ERROR_REQUIRES_ENCRYPTION_KEY = "requires_encryption_key"
ERROR_INVALID_ENCRYPTION_KEY = "invalid_psk"
ESPHOME_URL = "https://esphome.io/"
_LOGGER = logging.getLogger(__name__)

ZERO_NOISE_PSK = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


class EsphomeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a esphome config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._port: int | None = None
        self._password: str | None = None
        self._noise_required: bool | None = None
        self._noise_psk: str | None = None
        self._device_info: DeviceInfo | None = None
        self._reauth_entry: ConfigEntry | None = None
        # The ESPHome name as per its config
        self._device_name: str | None = None

    async def _async_step_user_base(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self._async_step_user_base(user_input=user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
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

    async def _async_try_fetch_device_info(self) -> ConfigFlowResult:
        """Try to fetch device info and return any errors."""
        response: str | None
        if self._noise_required:
            # If we already know we need encryption, don't try to fetch device info
            # without encryption.
            response = ERROR_REQUIRES_ENCRYPTION_KEY
        else:
            # After 2024.08, stop trying to fetch device info without encryption
            # so we can avoid probe requests to check for password. At this point
            # most devices should announce encryption support and password is
            # deprecated and can be discovered by trying to connect only after they
            # interact with the flow since it is expected to be a rare case.
            response = await self.fetch_device_info()

        if response == ERROR_REQUIRES_ENCRYPTION_KEY:
            if not self._device_name and not self._noise_psk:
                # If device name is not set we can send a zero noise psk
                # to get the device name which will allow us to populate
                # the device name and hopefully get the encryption key
                # from the dashboard.
                self._noise_psk = ZERO_NOISE_PSK
                response = await self.fetch_device_info()
                self._noise_psk = None

            if (
                self._device_name
                and await self._retrieve_encryption_key_from_dashboard()
            ):
                response = await self.fetch_device_info()

            # If the fetched key is invalid, unset it again.
            if response == ERROR_INVALID_ENCRYPTION_KEY:
                self._noise_psk = None
                response = ERROR_REQUIRES_ENCRYPTION_KEY

        if response == ERROR_REQUIRES_ENCRYPTION_KEY:
            return await self.async_step_encryption_key()
        if response is not None:
            return await self._async_step_user_base(error=response)
        return await self._async_authenticate_or_add()

    async def _async_authenticate_or_add(self) -> ConfigFlowResult:
        # Only show authentication step if device uses password
        assert self._device_info is not None
        if self._device_info.uses_password:
            return await self.async_step_authenticate()

        self._password = ""
        return self._async_get_entry()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self._async_try_fetch_device_info()
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name}
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
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
        self._noise_required = bool(discovery_info.properties.get("api_encryption"))

        # Check if already configured
        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )

        return await self.async_step_discovery_confirm()

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle MQTT discovery."""
        device_info = json_loads_object(discovery_info.payload)
        if "mac" not in device_info:
            return self.async_abort(reason="mqtt_missing_mac")

        # there will be no port if the API is not enabled
        if "port" not in device_info:
            return self.async_abort(reason="mqtt_missing_api")

        if "ip" not in device_info:
            return self.async_abort(reason="mqtt_missing_ip")

        # mac address is lowercase and without :, normalize it
        unformatted_mac = cast(str, device_info["mac"])
        mac_address = format_mac(unformatted_mac)

        device_name = cast(str, device_info["name"])

        self._device_name = device_name
        self._name = cast(str, device_info.get("friendly_name", device_name))
        self._host = cast(str, device_info["ip"])
        self._port = cast(int, device_info["port"])

        self._noise_required = "api_encryption" in device_info

        # Check if already configured
        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )

        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        # This should never happen since we only listen to DHCP requests
        # for configured devices.
        return self.async_abort(reason="already_configured")

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle Supervisor service discovery."""
        await async_set_dashboard_info(
            self.hass,
            discovery_info.slug,
            discovery_info.config["host"],
            discovery_info.config["port"],
        )
        return self.async_abort(reason="service_received")

    @callback
    def _async_get_entry(self) -> ConfigFlowResult:
        config_data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            # The API uses protobuf, so empty string denotes absence
            CONF_PASSWORD: self._password or "",
            CONF_NOISE_PSK: self._noise_psk or "",
            CONF_DEVICE_NAME: self._device_name,
        }
        config_options = {
            CONF_ALLOW_SERVICE_CALLS: DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
        }
        if self._reauth_entry:
            return self.async_update_reload_and_abort(
                self._reauth_entry, data=self._reauth_entry.data | config_data
            )

        assert self._name is not None
        return self.async_create_entry(
            title=self._name,
            data=config_data,
            options=config_options,
        )

    async def async_step_encryption_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
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
        except InvalidEncryptionKeyAPIError as ex:
            if ex.received_name:
                self._device_name = ex.received_name
                self._name = ex.received_name
            return ERROR_INVALID_ENCRYPTION_KEY
        except ResolveAPIError:
            return "resolve_error"
        except APIConnectionError:
            return "connection_error"
        finally:
            await cli.disconnect(force=True)

        self._name = self._device_info.friendly_name or self._device_info.name
        self._device_name = self._device_info.name
        mac_address = format_mac(self._device_info.mac_address)
        await self.async_set_unique_id(mac_address, raise_on_progress=False)
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
        if (
            self._device_name is None
            or (manager := await async_get_or_create_dashboard_manager(self.hass))
            is None
            or (dashboard := manager.async_get()) is None
        ):
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
        except json.JSONDecodeError:
            _LOGGER.exception("Error parsing response from dashboard")
            return False

        self._noise_psk = noise_psk
        return True

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for esphome."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ALLOW_SERVICE_CALLS,
                    default=self.config_entry.options.get(
                        CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
