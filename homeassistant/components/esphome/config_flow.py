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

from homeassistant.components import zeroconf
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util.json import json_loads_object

from .const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_DEVICE_NAME,
    CONF_NOISE_PSK,
    CONF_SUBSCRIBE_LOGS,
    DEFAULT_ALLOW_SERVICE_CALLS,
    DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
    DEFAULT_PORT,
    DOMAIN,
)
from .dashboard import async_get_or_create_dashboard_manager, async_set_dashboard_info
from .entry_data import ESPHomeConfigEntry
from .manager import async_replace_device

ERROR_REQUIRES_ENCRYPTION_KEY = "requires_encryption_key"
ERROR_INVALID_ENCRYPTION_KEY = "invalid_psk"
_LOGGER = logging.getLogger(__name__)

ZERO_NOISE_PSK = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
DEFAULT_NAME = "ESPHome"


class EsphomeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a esphome config flow."""

    VERSION = 1

    _reauth_entry: ConfigEntry
    _reconfig_entry: ConfigEntry

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self.__name: str | None = None
        self._port: int | None = None
        self._password: str | None = None
        self._noise_required: bool | None = None
        self._noise_psk: str | None = None
        self._device_info: DeviceInfo | None = None
        # The ESPHome name as per its config
        self._device_name: str | None = None
        self._device_mac: str | None = None
        self._entry_with_name_conflict: ConfigEntry | None = None

    async def _async_step_user_base(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            return await self._async_try_fetch_device_info()

        fields: dict[Any, type] = OrderedDict()
        fields[vol.Required(CONF_HOST, default=self._host or vol.UNDEFINED)] = str
        fields[vol.Optional(CONF_PORT, default=self._port or DEFAULT_PORT)] = int

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(fields),
            errors=errors,
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
        self._reauth_entry = self._get_reauth_entry()
        self._host = entry_data[CONF_HOST]
        self._port = entry_data[CONF_PORT]
        self._password = entry_data[CONF_PASSWORD]
        self._device_name = entry_data.get(CONF_DEVICE_NAME)
        self._name = self._reauth_entry.title

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

        if error is None and entry_data.get(CONF_NOISE_PSK):
            return await self.async_step_reauth_encryption_removed_confirm()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_encryption_removed_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow when encryption was removed."""
        if user_input is not None:
            self._noise_psk = None
            return await self._async_validated_connection()

        return self.async_show_form(
            step_id="reauth_encryption_removed_confirm",
            description_placeholders={"name": self._async_get_human_readable_name()},
        )

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
            description_placeholders={"name": self._async_get_human_readable_name()},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by a reconfig request."""
        self._reconfig_entry = self._get_reconfigure_entry()
        data = self._reconfig_entry.data
        self._host = data[CONF_HOST]
        self._port = data.get(CONF_PORT, DEFAULT_PORT)
        self._noise_psk = data.get(CONF_NOISE_PSK)
        self._device_name = data.get(CONF_DEVICE_NAME)
        return await self._async_step_user_base()

    @property
    def _name(self) -> str:
        return self.__name or DEFAULT_NAME

    @_name.setter
    def _name(self, value: str) -> None:
        self.__name = value
        self.context["title_placeholders"] = {
            "name": self._async_get_human_readable_name()
        }

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
        return await self._async_validated_connection()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self._async_try_fetch_device_info()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._async_get_human_readable_name()},
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
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

        self._device_name = device_name
        self._name = discovery_info.properties.get("friendly_name", device_name)
        self._host = discovery_info.host
        self._port = discovery_info.port
        self._noise_required = bool(discovery_info.properties.get("api_encryption"))

        # Check if already configured
        await self.async_set_unique_id(mac_address)
        await self._async_validate_mac_abort_configured(
            mac_address, self._host, self._port
        )
        return await self.async_step_discovery_confirm()

    async def _async_validate_mac_abort_configured(
        self, formatted_mac: str, host: str, port: int | None
    ) -> None:
        """Validate if the MAC address is already configured."""
        assert self.unique_id is not None
        if not (
            entry := self.hass.config_entries.async_entry_for_domain_unique_id(
                self.handler, formatted_mac
            )
        ):
            return
        if entry.source == SOURCE_IGNORE:
            # Don't call _fetch_device_info() for ignored entries
            raise AbortFlow("already_configured")
        configured_host: str | None = entry.data.get(CONF_HOST)
        configured_port: int | None = entry.data.get(CONF_PORT)
        if configured_host == host and configured_port == port:
            # Don't probe to verify the mac is correct since
            # the host and port matches.
            raise AbortFlow("already_configured")
        configured_psk: str | None = entry.data.get(CONF_NOISE_PSK)
        await self._fetch_device_info(host, port or configured_port, configured_psk)
        updates: dict[str, Any] = {}
        if self._device_mac == formatted_mac:
            updates[CONF_HOST] = host
            if port is not None:
                updates[CONF_PORT] = port
        self._abort_unique_id_configured_with_details(updates=updates)

    @callback
    def _abort_unique_id_configured_with_details(self, updates: dict[str, Any]) -> None:
        """Abort if unique_id is already configured with details."""
        assert self.unique_id is not None
        if not (
            conflict_entry := self.hass.config_entries.async_entry_for_domain_unique_id(
                self.handler, self.unique_id
            )
        ):
            return
        assert conflict_entry.unique_id is not None
        if self.source == SOURCE_RECONFIGURE:
            error = "reconfigure_already_configured"
        elif updates:
            error = "already_configured_updates"
        else:
            error = "already_configured_detailed"
        self._abort_if_unique_id_configured(
            updates=updates,
            error=error,
            description_placeholders={
                "title": conflict_entry.title,
                "name": conflict_entry.data.get(CONF_DEVICE_NAME, "unknown"),
                "mac": format_mac(conflict_entry.unique_id),
            },
        )

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle MQTT discovery."""
        if not discovery_info.payload:
            return self.async_abort(reason="mqtt_missing_payload")

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
        self._abort_unique_id_configured_with_details(
            updates={CONF_HOST: self._host, CONF_PORT: self._port}
        )

        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        mac_address = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(format_mac(mac_address))
        await self._async_validate_mac_abort_configured(
            mac_address, discovery_info.ip, None
        )
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

    async def async_step_name_conflict(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle name conflict resolution."""
        assert self._entry_with_name_conflict is not None
        assert self._entry_with_name_conflict.unique_id is not None
        assert self.unique_id is not None
        assert self._device_name is not None
        return self.async_show_menu(
            step_id="name_conflict",
            menu_options=["name_conflict_migrate", "name_conflict_overwrite"],
            description_placeholders={
                "existing_mac": format_mac(self._entry_with_name_conflict.unique_id),
                "existing_title": self._entry_with_name_conflict.title,
                "mac": format_mac(self.unique_id),
                "name": self._device_name,
            },
        )

    async def async_step_name_conflict_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle migration of existing entry."""
        assert self._entry_with_name_conflict is not None
        assert self._entry_with_name_conflict.unique_id is not None
        assert self.unique_id is not None
        assert self._device_name is not None
        assert self._host is not None
        old_mac = format_mac(self._entry_with_name_conflict.unique_id)
        new_mac = format_mac(self.unique_id)
        entry_id = self._entry_with_name_conflict.entry_id
        self.hass.config_entries.async_update_entry(
            self._entry_with_name_conflict,
            data={
                **self._entry_with_name_conflict.data,
                CONF_HOST: self._host,
                CONF_PORT: self._port or DEFAULT_PORT,
                CONF_PASSWORD: self._password or "",
                CONF_NOISE_PSK: self._noise_psk or "",
            },
        )
        await async_replace_device(self.hass, entry_id, old_mac, new_mac)
        self.hass.config_entries.async_schedule_reload(entry_id)
        return self.async_abort(
            reason="name_conflict_migrated",
            description_placeholders={
                "existing_mac": old_mac,
                "mac": new_mac,
                "name": self._device_name,
            },
        )

    async def async_step_name_conflict_overwrite(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle creating a new entry by removing the old one and creating new."""
        assert self._entry_with_name_conflict is not None
        await self.hass.config_entries.async_remove(
            self._entry_with_name_conflict.entry_id
        )
        return self._async_create_entry()

    @callback
    def _async_create_entry(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._name is not None
        return self.async_create_entry(
            title=self._name,
            data=self._async_make_config_data(),
            options={
                CONF_ALLOW_SERVICE_CALLS: DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS,
            },
        )

    @callback
    def _async_make_config_data(self) -> dict[str, Any]:
        """Return config data for the entry."""
        return {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            # The API uses protobuf, so empty string denotes absence
            CONF_PASSWORD: self._password or "",
            CONF_NOISE_PSK: self._noise_psk or "",
            CONF_DEVICE_NAME: self._device_name,
        }

    async def _async_validated_connection(self) -> ConfigFlowResult:
        """Handle validated connection."""
        if self.source == SOURCE_RECONFIGURE:
            return await self._async_reconfig_validated_connection()
        if self.source == SOURCE_REAUTH:
            return await self._async_reauth_validated_connection()
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data.get(CONF_DEVICE_NAME) == self._device_name:
                self._entry_with_name_conflict = entry
                return await self.async_step_name_conflict()
        return self._async_create_entry()

    async def _async_reauth_validated_connection(self) -> ConfigFlowResult:
        """Handle reauth validated connection."""
        assert self._reauth_entry.unique_id is not None
        if self.unique_id == self._reauth_entry.unique_id:
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data=self._reauth_entry.data | self._async_make_config_data(),
            )
        assert self._host is not None
        self._abort_unique_id_configured_with_details(
            updates={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_NOISE_PSK: self._noise_psk,
            }
        )
        # Reauth was triggered a while ago, and since than
        # a new device resides at the same IP address.
        assert self._device_name is not None
        return self.async_abort(
            reason="reauth_unique_id_changed",
            description_placeholders={
                "name": self._reauth_entry.data.get(
                    CONF_DEVICE_NAME, self._reauth_entry.title
                ),
                "host": self._host,
                "expected_mac": format_mac(self._reauth_entry.unique_id),
                "unexpected_mac": format_mac(self.unique_id),
                "unexpected_device_name": self._device_name,
            },
        )

    async def _async_reconfig_validated_connection(self) -> ConfigFlowResult:
        """Handle reconfigure validated connection."""
        assert self._reconfig_entry.unique_id is not None
        assert self._host is not None
        assert self._device_name is not None
        if not (
            unique_id_matches := (self.unique_id == self._reconfig_entry.unique_id)
        ):
            self._abort_unique_id_configured_with_details(
                updates={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_NOISE_PSK: self._noise_psk,
                }
            )
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.entry_id != self._reconfig_entry.entry_id
                and entry.data.get(CONF_DEVICE_NAME) == self._device_name
            ):
                return self.async_abort(
                    reason="reconfigure_name_conflict",
                    description_placeholders={
                        "name": self._reconfig_entry.data[CONF_DEVICE_NAME],
                        "host": self._host,
                        "expected_mac": format_mac(self._reconfig_entry.unique_id),
                        "existing_title": entry.title,
                    },
                )
        if unique_id_matches:
            return self.async_update_reload_and_abort(
                self._reconfig_entry,
                data=self._reconfig_entry.data | self._async_make_config_data(),
            )
        if self._reconfig_entry.data.get(CONF_DEVICE_NAME) == self._device_name:
            self._entry_with_name_conflict = self._reconfig_entry
            return await self.async_step_name_conflict()
        return self.async_abort(
            reason="reconfigure_unique_id_changed",
            description_placeholders={
                "name": self._reconfig_entry.data.get(
                    CONF_DEVICE_NAME, self._reconfig_entry.title
                ),
                "host": self._host,
                "expected_mac": format_mac(self._reconfig_entry.unique_id),
                "unexpected_mac": format_mac(self.unique_id),
                "unexpected_device_name": self._device_name,
            },
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
            description_placeholders={"name": self._async_get_human_readable_name()},
        )

    @callback
    def _async_get_human_readable_name(self) -> str:
        """Return a human readable name for the entry."""
        entry: ConfigEntry | None = None
        if self.source == SOURCE_REAUTH:
            entry = self._reauth_entry
        elif self.source == SOURCE_RECONFIGURE:
            entry = self._reconfig_entry
        friendly_name = self._name
        device_name = self._device_name
        if (
            device_name
            and friendly_name in (DEFAULT_NAME, device_name)
            and entry
            and entry.title != friendly_name
        ):
            friendly_name = entry.title
        if not device_name or friendly_name == device_name:
            return friendly_name
        return f"{friendly_name} ({device_name})"

    async def async_step_authenticate(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> ConfigFlowResult:
        """Handle getting password for authentication."""
        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            error = await self.try_login()
            if error:
                return await self.async_step_authenticate(error=error)
            return await self._async_validated_connection()

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="authenticate",
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"name": self._async_get_human_readable_name()},
            errors=errors,
        )

    async def _fetch_device_info(
        self, host: str, port: int | None, noise_psk: str | None
    ) -> str | None:
        """Fetch device info from API and return any errors."""
        zeroconf_instance = await zeroconf.async_get_instance(self.hass)
        cli = APIClient(
            host,
            port or DEFAULT_PORT,
            "",
            zeroconf_instance=zeroconf_instance,
            noise_psk=noise_psk,
        )
        try:
            await cli.connect()
            self._device_info = await cli.device_info()
        except RequiresEncryptionAPIError:
            return ERROR_REQUIRES_ENCRYPTION_KEY
        except InvalidEncryptionKeyAPIError as ex:
            if ex.received_name:
                device_name_changed = self._device_name != ex.received_name
                self._device_name = ex.received_name
                if ex.received_mac:
                    self._device_mac = format_mac(ex.received_mac)
                if not self._name or device_name_changed:
                    self._name = ex.received_name
            return ERROR_INVALID_ENCRYPTION_KEY
        except ResolveAPIError:
            return "resolve_error"
        except APIConnectionError:
            return "connection_error"
        finally:
            await cli.disconnect(force=True)
        self._device_mac = format_mac(self._device_info.mac_address)
        self._device_name = self._device_info.name
        self._name = self._device_info.friendly_name or self._device_info.name
        return None

    async def fetch_device_info(self) -> str | None:
        """Fetch device info from API and return any errors."""
        assert self._host is not None
        assert self._port is not None
        if error := await self._fetch_device_info(
            self._host, self._port, self._noise_psk
        ):
            return error
        assert self._device_info is not None
        mac_address = format_mac(self._device_info.mac_address)
        await self.async_set_unique_id(mac_address, raise_on_progress=False)
        if self.source not in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            self._abort_unique_id_configured_with_details(
                updates={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_NOISE_PSK: self._noise_psk,
                }
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
        config_entry: ESPHomeConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for esphome."""

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
                vol.Required(
                    CONF_SUBSCRIBE_LOGS,
                    default=self.config_entry.options.get(CONF_SUBSCRIBE_LOGS, False),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
