"""Config flow for TP-Link."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, Self, cast

from kasa import (
    AuthenticationError,
    Credentials,
    Device,
    DeviceConfig,
    Discover,
    KasaException,
    Module,
    TimeoutError,
)
import voluptuous as vol

from homeassistant.components import ffmpeg, stream
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_ALIAS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.typing import DiscoveryInfoType

from . import (
    async_discover_devices,
    create_async_tplink_clientsession,
    get_credentials,
    mac_alias,
    set_credentials,
)
from .const import (
    CONF_AES_KEYS,
    CONF_CAMERA_CREDENTIALS,
    CONF_CONFIG_ENTRY_MINOR_VERSION,
    CONF_CONNECTION_PARAMETERS,
    CONF_CREDENTIALS_HASH,
    CONF_LIVE_VIEW,
    CONF_USES_HTTP,
    CONNECT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

STEP_CAMERA_AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LIVE_VIEW): bool,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class TPLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for tplink."""

    VERSION = 1
    MINOR_VERSION = CONF_CONFIG_ENTRY_MINOR_VERSION

    host: str | None = None
    port: int | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, Device] = {}
        self._discovered_device: Device | None = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        return await self._async_handle_discovery(
            discovery_info.ip, dr.format_mac(discovery_info.macaddress)
        )

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        return await self._async_handle_discovery(
            discovery_info[CONF_HOST],
            discovery_info[CONF_MAC],
            discovery_info[CONF_DEVICE],
        )

    @callback
    def _get_config_updates(
        self, entry: ConfigEntry, host: str, device: Device | None
    ) -> dict | None:
        """Return updates if the host or device config has changed."""
        entry_data = entry.data
        updates: dict[str, Any] = {}
        new_connection_params = False
        if entry_data[CONF_HOST] != host:
            updates[CONF_HOST] = host
        if device:
            device_conn_params_dict = device.config.connection_type.to_dict()
            entry_conn_params_dict = entry_data.get(CONF_CONNECTION_PARAMETERS)
            if device_conn_params_dict != entry_conn_params_dict:
                new_connection_params = True
                updates[CONF_CONNECTION_PARAMETERS] = device_conn_params_dict
                updates[CONF_USES_HTTP] = device.config.uses_http
        if not updates:
            return None
        updates = {**entry.data, **updates}
        # If the connection parameters have changed the credentials_hash will be invalid.
        if new_connection_params:
            updates.pop(CONF_CREDENTIALS_HASH, None)
            _LOGGER.debug(
                "Connection type changed for %s from %s to: %s",
                host,
                entry_conn_params_dict,
                device_conn_params_dict,
            )
        return updates

    @callback
    def _update_config_if_entry_in_setup_error(
        self, entry: ConfigEntry, host: str, device: Device | None
    ) -> ConfigFlowResult | None:
        """If discovery encounters a device that is in SETUP_ERROR or SETUP_RETRY update the device config."""
        if entry.state not in (
            ConfigEntryState.SETUP_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ):
            return None
        if updates := self._get_config_updates(entry, host, device):
            return self.async_update_reload_and_abort(
                entry,
                data=updates,
                reason="already_configured",
            )
        return None

    async def _async_handle_discovery(
        self, host: str, formatted_mac: str, device: Device | None = None
    ) -> ConfigFlowResult:
        """Handle any discovery."""
        current_entry = await self.async_set_unique_id(
            formatted_mac, raise_on_progress=False
        )
        if current_entry and (
            result := self._update_config_if_entry_in_setup_error(
                current_entry, host, device
            )
        ):
            return result
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})
        self.host = host
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")
        credentials = await get_credentials(self.hass)
        try:
            # If integration discovery there will be a device or None for dhcp
            if device:
                self._discovered_device = device
                await self._async_try_connect(device, credentials)
            else:
                await self._async_try_discover_and_update(
                    host,
                    credentials,
                    raise_on_progress=True,
                    raise_on_timeout=True,
                )
        except AuthenticationError:
            return await self.async_step_discovery_auth_confirm()
        except KasaException:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_discovery_confirm()

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        return other_flow.host == self.host

    async def async_step_discovery_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that auth is required."""
        assert self._discovered_device is not None
        errors = {}

        credentials = await get_credentials(self.hass)
        if credentials and credentials != self._discovered_device.config.credentials:
            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationError:
                pass  # Authentication exceptions should continue to the rest of the step
            else:
                self._discovered_device = device
                return await self.async_step_discovery_confirm()

        placeholders = self._async_make_placeholders_from_discovery()

        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            credentials = Credentials(username, password)
            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationError as ex:
                errors[CONF_PASSWORD] = "invalid_auth"
                placeholders["error"] = str(ex)
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                self._discovered_device = device
                await set_credentials(self.hass, username, password)
                self.hass.async_create_task(
                    self._async_reload_requires_auth_entries(), eager_start=False
                )
                if self._async_supports_camera_credentials(device):
                    return await self.async_step_camera_auth_confirm()

                return self._async_create_or_update_entry_from_device(
                    self._discovered_device
                )

        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_auth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    def _async_make_placeholders_from_discovery(self) -> dict[str, str]:
        """Make placeholders for the discovery steps."""
        discovered_device = self._discovered_device
        assert discovered_device is not None
        return {
            "name": discovered_device.alias or mac_alias(discovered_device.mac),
            "model": discovered_device.model,
            "host": discovered_device.host,
        }

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        if user_input is not None:
            if self._async_supports_camera_credentials(self._discovered_device):
                return await self.async_step_camera_auth_confirm()

            return self._async_create_or_update_entry_from_device(
                self._discovered_device
            )

        self._set_confirm_only()
        placeholders = self._async_make_placeholders_from_discovery()
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    @staticmethod
    def _async_get_host_port(host_str: str) -> tuple[str, int | None]:
        """Parse the host string for host and port."""
        if "[" in host_str:
            _, _, bracketed = host_str.partition("[")
            host, _, port_str = bracketed.partition("]")
            _, _, port_str = port_str.partition(":")
        else:
            host, _, port_str = host_str.partition(":")

        if not port_str:
            return host, None

        try:
            port = int(port_str)
        except ValueError:
            return host, None

        return host, port

    def _async_supports_camera_credentials(self, device: Device) -> bool:
        """Return True if device could have separate camera credentials."""
        if camera_module := device.modules.get(Module.Camera):
            self._discovered_device = device
            return bool(camera_module.stream_rtsp_url())
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            if not (host := user_input[CONF_HOST]):
                return await self.async_step_pick_device()

            host, port = self._async_get_host_port(host)

            match_dict: dict[str, Any] = {CONF_HOST: host}
            if port:
                self.port = port
                match_dict[CONF_PORT] = port
            self._async_abort_entries_match(match_dict)

            self.host = host
            credentials = await get_credentials(self.hass)
            try:
                device = await self._async_try_discover_and_update(
                    host,
                    credentials,
                    raise_on_progress=False,
                    raise_on_timeout=False,
                    port=port,
                ) or await self._async_try_connect_all(
                    host,
                    credentials=credentials,
                    raise_on_progress=False,
                    port=port,
                )
            except AuthenticationError:
                return await self.async_step_user_auth_confirm()
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                if not device:
                    return await self.async_step_user_auth_confirm()

                if self._async_supports_camera_credentials(device):
                    return await self.async_step_camera_auth_confirm()

                return self._async_create_or_update_entry_from_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_user_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that auth is required."""
        errors: dict[str, str] = {}
        if TYPE_CHECKING:
            # self.host is set by async_step_user and async_step_pick_device
            assert self.host is not None
        placeholders: dict[str, str] = {CONF_HOST: self.host}

        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            credentials = Credentials(username, password)
            device: Device | None
            try:
                if self._discovered_device:
                    device = await self._async_try_connect(
                        self._discovered_device, credentials
                    )
                else:
                    device = await self._async_try_connect_all(
                        self.host,
                        credentials=credentials,
                        raise_on_progress=False,
                        port=self.port,
                    )
            except AuthenticationError as ex:
                errors[CONF_PASSWORD] = "invalid_auth"
                placeholders["error"] = str(ex)
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                if not device:
                    errors["base"] = "cannot_connect"
                    placeholders["error"] = "try_connect_all failed"
                else:
                    await set_credentials(self.hass, username, password)
                    self.hass.async_create_task(
                        self._async_reload_requires_auth_entries(), eager_start=False
                    )
                    if self._async_supports_camera_credentials(device):
                        return await self.async_step_camera_auth_confirm()

                    return self._async_create_or_update_entry_from_device(device)

        return self.async_show_form(
            step_id="user_auth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    def _create_camera_entry(
        self, device: Device, un: str, pw: str
    ) -> ConfigFlowResult:
        entry_data: dict[str, bool | dict[str, str]] = {CONF_LIVE_VIEW: True}
        entry_data[CONF_CAMERA_CREDENTIALS] = {
            CONF_USERNAME: un,
            CONF_PASSWORD: pw,
        }
        _LOGGER.debug("Creating camera account entry for device %s", device.host)
        return self._async_create_or_update_entry_from_device(
            device, camera_data=entry_data
        )

    async def async_step_camera_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that gives the user option to set camera credentials."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        device = self._discovered_device
        assert device

        if user_input:
            live_view = user_input[CONF_LIVE_VIEW]
            if not live_view:
                return self._async_create_or_update_entry_from_device(
                    device, camera_data={CONF_LIVE_VIEW: False}
                )

            un = user_input.get(CONF_USERNAME)
            pw = user_input.get(CONF_PASSWORD)

        if user_input and un and pw:
            camera_creds = Credentials(un, cast(str, pw))

            camera_module = device.modules[Module.Camera]
            rtsp_url = camera_module.stream_rtsp_url(camera_creds)
            assert rtsp_url

            # If camera fails to create HLS stream via 'stream' then try
            # ffmpeg.async_get_image as some cameras do not work with HLS
            # and the frontend will fallback to mpeg on error
            try:
                await stream.async_check_stream_client_error(self.hass, rtsp_url)
            except stream.StreamOpenClientError as ex:
                if ex.error_code is stream.StreamClientError.Unauthorized:
                    errors["base"] = "invalid_camera_auth"
                else:
                    _LOGGER.debug(
                        "Device %s client error checking stream: %s", device.host, ex
                    )
                    if await ffmpeg.async_get_image(self.hass, rtsp_url):
                        return self._create_camera_entry(device, un, pw)

                    errors["base"] = "cannot_connect_camera"
                    placeholders["error"] = str(ex)
            except Exception as ex:  # noqa: BLE001
                _LOGGER.debug("Device %s error checking stream: %s", device.host, ex)
                if await ffmpeg.async_get_image(self.hass, rtsp_url):
                    return self._create_camera_entry(device, un, pw)

                errors["base"] = "cannot_connect_camera"
                placeholders["error"] = str(ex)
            else:
                return self._create_camera_entry(device, un, pw)

        elif user_input:
            errors["base"] = "camera_creds"

        entry = None
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
        elif self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()

        if entry:
            placeholders[CONF_NAME] = entry.data[CONF_ALIAS]
            placeholders[CONF_MODEL] = entry.data[CONF_MODEL]
            placeholders[CONF_HOST] = entry.data[CONF_HOST]

        if user_input:
            form_data = {**user_input}
        elif entry:
            form_data = {**entry.data.get(CONF_CAMERA_CREDENTIALS, {})}
            form_data[CONF_LIVE_VIEW] = entry.data.get(CONF_LIVE_VIEW, False)
        else:
            form_data = {}

        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="camera_auth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_CAMERA_AUTH_DATA_SCHEMA, form_data
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            mac = user_input[CONF_DEVICE]
            await self.async_set_unique_id(mac, raise_on_progress=False)
            self._discovered_device = self._discovered_devices[mac]
            self.host = self._discovered_device.host
            credentials = await get_credentials(self.hass)

            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationError:
                return await self.async_step_user_auth_confirm()
            except KasaException:
                return self.async_abort(reason="cannot_connect")

            if self._async_supports_camera_credentials(device):
                return await self.async_step_camera_auth_confirm()

            return self._async_create_or_update_entry_from_device(device)

        configured_devices = {
            entry.unique_id for entry in self._async_current_entries()
        }
        self._discovered_devices = await async_discover_devices(self.hass)
        devices_name = {
            formatted_mac: (
                f"{device.alias or mac_alias(device.mac)} {device.model} ({device.host}) {formatted_mac}"
            )
            for formatted_mac, device in self._discovered_devices.items()
            if formatted_mac not in configured_devices
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def _async_reload_requires_auth_entries(self) -> None:
        """Reload all config entries after auth update."""
        _config_entries = self.hass.config_entries

        if self.source == SOURCE_REAUTH:
            await _config_entries.async_reload(self._get_reauth_entry().entry_id)

        for flow in _config_entries.flow.async_progress_by_handler(
            DOMAIN, include_uninitialized=True
        ):
            context = flow["context"]
            if context.get("source") != SOURCE_REAUTH:
                continue
            entry_id = context["entry_id"]
            if entry := _config_entries.async_get_entry(entry_id):
                await _config_entries.async_reload(entry.entry_id)

    @callback
    def _async_create_or_update_entry_from_device(
        self, device: Device, *, camera_data: dict | None = None
    ) -> ConfigFlowResult:
        """Create a config entry from a smart device."""
        entry = None
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
        elif self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()

        if not entry:
            self._abort_if_unique_id_configured(updates={CONF_HOST: device.host})

        data: dict[str, Any] = {
            CONF_HOST: device.host,
            CONF_ALIAS: device.alias,
            CONF_MODEL: device.model,
            CONF_CONNECTION_PARAMETERS: device.config.connection_type.to_dict(),
            CONF_USES_HTTP: device.config.uses_http,
        }
        if camera_data is not None:
            data[CONF_LIVE_VIEW] = camera_data[CONF_LIVE_VIEW]
            if camera_creds := camera_data.get(CONF_CAMERA_CREDENTIALS):
                data[CONF_CAMERA_CREDENTIALS] = camera_creds

        if device.config.aes_keys:
            data[CONF_AES_KEYS] = device.config.aes_keys

        # This is only ever called after a successful device update so we know that
        # the credential_hash is correct and should be saved.
        if device.credentials_hash:
            data[CONF_CREDENTIALS_HASH] = device.credentials_hash
        if port := device.config.port_override:
            data[CONF_PORT] = port

        if not entry:
            return self.async_create_entry(
                title=f"{device.alias} {device.model}",
                data=data,
            )

        return self.async_update_reload_and_abort(entry, data=data)

    async def _async_try_connect_all(
        self,
        host: str,
        credentials: Credentials | None,
        raise_on_progress: bool,
        *,
        port: int | None = None,
    ) -> Device | None:
        """Try to connect to the device speculatively.

        The connection parameters aren't known but discovery has failed so try
        to connect with tcp.
        """
        if credentials:
            device = await Discover.try_connect_all(
                host,
                credentials=credentials,
                http_client=create_async_tplink_clientsession(self.hass),
                port=port,
            )
        else:
            # This will just try the legacy protocol that doesn't require auth
            # and doesn't use http
            try:
                device = await Device.connect(
                    config=DeviceConfig(host, port_override=port)
                )
            except Exception:  # noqa: BLE001
                return None
        if device:
            await self.async_set_unique_id(
                dr.format_mac(device.mac),
                raise_on_progress=raise_on_progress,
            )
        return device

    async def _async_try_discover_and_update(
        self,
        host: str,
        credentials: Credentials | None,
        raise_on_progress: bool,
        raise_on_timeout: bool,
        *,
        port: int | None = None,
    ) -> Device | None:
        """Try to discover the device and call update.

        Will try to connect directly if discovery fails.
        """
        self._discovered_device = None
        try:
            self._discovered_device = await Discover.discover_single(
                host,
                credentials=credentials,
                port=port,
            )
        except TimeoutError as ex:
            if raise_on_timeout:
                raise ex from ex
            return None
        if TYPE_CHECKING:
            assert self._discovered_device
        await self.async_set_unique_id(
            dr.format_mac(self._discovered_device.mac),
            raise_on_progress=raise_on_progress,
        )
        if self._discovered_device.config.uses_http:
            self._discovered_device.config.http_client = (
                create_async_tplink_clientsession(self.hass)
            )
        await self._discovered_device.update()
        return self._discovered_device

    async def _async_try_connect(
        self,
        discovered_device: Device,
        credentials: Credentials | None,
    ) -> Device:
        """Try to connect."""
        if self.source not in {SOURCE_RECONFIGURE, SOURCE_REAUTH}:
            self._async_abort_entries_match({CONF_HOST: discovered_device.host})

        config = discovered_device.config
        if credentials:
            config.credentials = credentials
        config.timeout = CONNECT_TIMEOUT
        if config.uses_http:
            config.http_client = create_async_tplink_clientsession(self.hass)

        self._discovered_device = await Device.connect(config=config)
        await self.async_set_unique_id(
            dr.format_mac(self._discovered_device.mac),
            raise_on_progress=False,
        )
        return self._discovered_device

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start the reauthentication flow if the device needs updated credentials."""
        if self.context.get("reauth_source") == CONF_CAMERA_CREDENTIALS:
            self._discovered_device = entry_data["device"]
            return await self.async_step_camera_auth_confirm()

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        entry_data = reauth_entry.data
        host = entry_data[CONF_HOST]
        port = entry_data.get(CONF_PORT)

        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            credentials = Credentials(username, password)
            try:
                device = await self._async_try_discover_and_update(
                    host,
                    credentials=credentials,
                    raise_on_progress=False,
                    raise_on_timeout=False,
                    port=port,
                ) or await self._async_try_connect_all(
                    host,
                    credentials=credentials,
                    raise_on_progress=False,
                    port=port,
                )
            except AuthenticationError as ex:
                errors[CONF_PASSWORD] = "invalid_auth"
                placeholders["error"] = str(ex)
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                if not device:
                    errors["base"] = "cannot_connect"
                    placeholders["error"] = "try_connect_all failed"
                else:
                    await self.async_set_unique_id(
                        dr.format_mac(device.mac),
                        raise_on_progress=False,
                    )
                    await set_credentials(self.hass, username, password)
                    if updates := self._get_config_updates(reauth_entry, host, device):
                        self.hass.config_entries.async_update_entry(
                            reauth_entry, data=updates
                        )
                    self.hass.async_create_task(
                        self._async_reload_requires_auth_entries(), eager_start=False
                    )
                    return self.async_abort(reason="reauth_successful")

        # Old config entries will not have these values.
        alias = entry_data.get(CONF_ALIAS) or "unknown"
        model = entry_data.get(CONF_MODEL) or "unknown"

        placeholders.update({"name": alias, "model": model, "host": host})

        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Trigger a reconfiguration flow."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        reconfigure_entry = self._get_reconfigure_entry()
        assert reconfigure_entry.unique_id
        await self.async_set_unique_id(reconfigure_entry.unique_id)

        host = reconfigure_entry.data[CONF_HOST]
        port = reconfigure_entry.data.get(CONF_PORT)

        if user_input is not None:
            host, port = self._async_get_host_port(host)

            self.host = host
            credentials = await get_credentials(self.hass)
            try:
                device = await self._async_try_discover_and_update(
                    host,
                    credentials,
                    raise_on_progress=False,
                    raise_on_timeout=False,
                    port=port,
                ) or await self._async_try_connect_all(
                    host,
                    credentials=credentials,
                    raise_on_progress=False,
                    port=port,
                )
            except AuthenticationError:  # Error from the update()
                return await self.async_step_user_auth_confirm()
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                if not device:
                    return await self.async_step_user_auth_confirm()

                if self._async_supports_camera_credentials(device):
                    return await self.async_step_camera_auth_confirm()

                return self._async_create_or_update_entry_from_device(device)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA,
                {CONF_HOST: f"{host}:{port}" if port else host},
            ),
            errors=errors,
            description_placeholders={
                **placeholders,
                CONF_MAC: reconfigure_entry.unique_id,
            },
        )
