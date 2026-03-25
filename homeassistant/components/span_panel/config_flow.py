"""Span Panel Config Flow."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import enum
import logging
from typing import TYPE_CHECKING, Any

from span_panel_api import (
    V2AuthResponse,
    delete_fqdn,
    detect_api_version,
    register_fqdn,
)
from span_panel_api.exceptions import (
    SpanPanelAPIError,
    SpanPanelAuthError,
    SpanPanelConnectionError,
    SpanPanelTimeoutError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowContext,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util.network import is_ipv4_address

from .config_flow_options import (
    build_general_options_schema,
    get_general_options_defaults,
    process_general_options_input,
)
from .config_flow_validation import (
    check_fqdn_tls_ready,
    is_fqdn,
    validate_host,
    validate_v2_passphrase,
    validate_v2_proximity,
)
from .const import (
    CONF_API_VERSION,
    CONF_EBUS_BROKER_HOST,
    CONF_EBUS_BROKER_PASSWORD,
    CONF_EBUS_BROKER_PORT,
    CONF_EBUS_BROKER_USERNAME,
    CONF_HOP_PASSPHRASE,
    CONF_HTTP_PORT,
    CONF_PANEL_SERIAL,
    CONF_REGISTERED_FQDN,
    DOMAIN,
    ENABLE_ENERGY_DIP_COMPENSATION,
    ENTITY_NAMING_PATTERN,
    USE_CIRCUIT_NUMBERS,
    USE_DEVICE_PREFIX,
    EntityNamingPattern,
)
from .options import (
    ENERGY_DISPLAY_PRECISION,
    ENERGY_REPORTING_GRACE_PERIOD,
    POWER_DISPLAY_PRECISION,
    SNAPSHOT_UPDATE_INTERVAL,
)

if TYPE_CHECKING:
    from . import SpanPanelConfigEntry

_LOGGER = logging.getLogger(__name__)


class ConfigFlowError(Exception):
    """Custom exception for config flow internal errors."""


def get_user_data_schema(default_host: str = "") -> vol.Schema:
    """Get the user data schema with optional default host."""
    return vol.Schema(
        {
            vol.Optional(CONF_HOST, default=default_host): str,
            vol.Optional(CONF_HTTP_PORT, default=80): int,
            vol.Optional(POWER_DISPLAY_PRECISION, default=0): int,
            vol.Optional(ENERGY_DISPLAY_PRECISION, default=2): int,
            vol.Optional(ENABLE_ENERGY_DIP_COMPENSATION, default=True): bool,
        }
    )


STEP_USER_DATA_SCHEMA = get_user_data_schema()

STEP_AUTH_PASSPHRASE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOP_PASSPHRASE): str,
    }
)


class TriggerFlowType(enum.Enum):
    """Types of configuration flow triggers."""

    CREATE_ENTRY = enum.auto()
    UPDATE_ENTRY = enum.auto()


class SpanPanelConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Span Panel."""

    VERSION = 6
    MINOR_VERSION = 1
    domain = DOMAIN

    def is_matching(self, other_flow: SpanPanelConfigFlow) -> bool:
        """Return True if other_flow is a matching Span Panel."""
        return bool(other_flow and other_flow.context.get("source") == "zeroconf")

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.trigger_flow_type: TriggerFlowType | None = None
        self.host: str | None = None
        self.serial_number: str | None = None
        self.access_token: str | None = None
        self.power_display_precision: int = 0
        self.energy_display_precision: int = 2
        self._is_flow_setup: bool = False
        self.context: ConfigFlowContext = {}
        # Initial naming selection chosen during pre-setup
        self._chosen_use_device_prefix: bool | None = None
        self._chosen_use_circuit_numbers: bool | None = None
        # v2 provisioning state
        self.api_version: str = "v2"
        self._v2_broker_host: str | None = None
        self._v2_broker_port: int | None = None
        self._v2_broker_username: str | None = None
        self._v2_broker_password: str | None = None
        self._v2_passphrase: str | None = None
        self._v2_panel_serial: str | None = None
        self._http_port: int = 80
        # Energy dip compensation default for fresh installs
        self._enable_dip_compensation: bool = True
        # FQDN registration task (async_show_progress)
        self._fqdn_task: asyncio.Task[None] | None = None
        self._reconfigure_fqdn_task: asyncio.Task[None] | None = None

    def ensure_flow_is_set_up(self) -> None:
        """Ensure the flow is set up."""
        if self._is_flow_setup is False:
            _LOGGER.error("Flow method called before setup")
            raise ConfigFlowError("Flow is not set up")

    async def ensure_not_already_configured(
        self, raise_on_progress: bool = True
    ) -> None:
        """Ensure the panel is not already configured."""
        self.ensure_flow_is_set_up()

        # Abort if we had already set this panel up.
        # User-initiated flows pass raise_on_progress=False so they can
        # proceed when a zeroconf discovery flow is already running.
        await self.async_set_unique_id(
            self.serial_number, raise_on_progress=raise_on_progress
        )
        self._abort_if_unique_id_configured(updates={CONF_HOST: self.host})

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf discovery."""
        # Do not probe device if the host is already configured
        self._async_abort_entries_match({CONF_HOST: discovery_info.host})

        # Do not probe device if it is not an ipv4 address
        if not is_ipv4_address(discovery_info.host):
            return self.async_abort(reason="not_ipv4_address")

        # Set a preliminary unique_id from the host to prevent duplicate
        # in-progress discovery flows when mDNS fires repeatedly for the
        # same IP. The default raise_on_progress=True causes subsequent
        # flows for the same host to abort immediately with
        # "already_in_progress". This is replaced with the serial number
        # in ensure_not_already_configured() once the device is validated.
        await self.async_set_unique_id(discovery_info.host)

        # Detect whether this is a v2 panel based on zeroconf service type
        svc_type = getattr(discovery_info, "type", "") or ""
        is_v2_service = svc_type in ("_ebus._tcp.local.", "_secure-mqtt._tcp.local.")

        if is_v2_service:
            # v2 panels discovered via eBus / secure-mqtt service types
            # Read optional httpPort from mDNS TXT records (non-standard port)
            props = discovery_info.properties or {}
            http_port_str = props.get("httpPort", props.get("httpport", ""))
            try:
                http_port = int(http_port_str) if http_port_str else 80
            except ValueError, TypeError:
                http_port = 80
            self._http_port = http_port

            detection = await detect_api_version(
                discovery_info.host,
                port=http_port,
                httpx_client=get_async_client(self.hass, verify_ssl=False),
            )
            if detection.api_version != "v2" or detection.status_info is None:
                return self.async_abort(reason="not_span_panel")
            self.api_version = "v2"
            self.host = discovery_info.host
            self.serial_number = detection.status_info.serial_number
            self.trigger_flow_type = TriggerFlowType.CREATE_ENTRY
            self.context = {
                **self.context,
                "title_placeholders": {
                    **self.context.get("title_placeholders", {}),
                    CONF_HOST: discovery_info.host,
                },
            }
            self._is_flow_setup = True
            await self.ensure_not_already_configured()
            return await self.async_step_confirm_discovery()

        # Non-v2 panels are not supported
        return self.async_abort(reason="v1_not_supported")

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery from Home Assistant Supervisor (add-on).

        Unlike zeroconf, several panels may be reachable on the same host IP
        on different HTTP ports (for example the SPAN Panel Simulator add-on).
        Deduplicate by panel serial, not by host, so each panel gets its own
        config entry.
        """
        config = discovery_info.config
        host = str(config.get("host", ""))
        port = int(config.get("port", 80))
        serial = str(config.get("serial", ""))

        if not host:
            return self.async_abort(reason="no_host")

        # Validate panel is reachable and v2
        self._http_port = port
        detection = await detect_api_version(
            host, port=port, httpx_client=get_async_client(self.hass, verify_ssl=False)
        )
        if detection.api_version != "v2" or detection.status_info is None:
            return self.async_abort(reason="not_span_panel")

        # Use the serial from the panel (prefer detected over discovery hint)
        panel_serial = detection.status_info.serial_number or serial
        if not panel_serial:
            return self.async_abort(reason="no_serial")

        # Dedup by serial — multiple panels may share the same host IP
        await self.async_set_unique_id(panel_serial)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host, CONF_HTTP_PORT: port}
        )

        # Set up flow — same path as v2 zeroconf discovery
        self.api_version = "v2"
        self.host = host
        self.serial_number = panel_serial
        self.trigger_flow_type = TriggerFlowType.CREATE_ENTRY
        self.context = {
            **self.context,
            "title_placeholders": {
                **self.context.get("title_placeholders", {}),
                CONF_HOST: panel_serial,
            },
        }
        self._is_flow_setup = True
        return await self.async_step_confirm_discovery()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        # Store precision settings from user input for later flow steps.
        self.power_display_precision = user_input.get(POWER_DISPLAY_PRECISION, 0)
        self.energy_display_precision = user_input.get(ENERGY_DISPLAY_PRECISION, 2)
        self._enable_dip_compensation = user_input.get(
            ENABLE_ENERGY_DIP_COMPENSATION, True
        )

        _LOGGER.debug(
            "CONFIG_INPUT_DEBUG: User input precision - power: %s, energy: %s, full input: %s",
            self.power_display_precision,
            self.energy_display_precision,
            user_input,
        )

        host: str = user_input.get(CONF_HOST, "").strip()
        self._http_port = int(user_input.get(CONF_HTTP_PORT, 80))
        if not host:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "host_required"},
            )

        # Validate host before setting up flow
        if not await validate_host(self.hass, host, port=self._http_port):
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        # Detect API version — only v2 is supported
        detection = await detect_api_version(
            host,
            port=self._http_port,
            httpx_client=get_async_client(self.hass, verify_ssl=False),
        )
        if detection.probe_failed:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "cannot_connect"},
            )
        self.api_version = detection.api_version

        if self.api_version == "v2":
            if detection.status_info is None:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "cannot_connect"},
                )
            # Serial comes from detection
            self.host = host
            self.serial_number = detection.status_info.serial_number
            self.trigger_flow_type = TriggerFlowType.CREATE_ENTRY
            self.context = {
                **self.context,
                "title_placeholders": {
                    **self.context.get("title_placeholders", {}),
                    CONF_HOST: host,
                },
            }
            self._is_flow_setup = True
            await self.ensure_not_already_configured(raise_on_progress=False)
            return await self.async_step_choose_v2_auth()

        # Non-v2 panels are not supported
        return self.async_abort(reason="v1_not_supported")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initiated by re-auth."""
        host = entry_data[CONF_HOST]
        self._http_port = int(entry_data.get(CONF_HTTP_PORT, 80))

        # Detect current API version of the panel
        detection = await detect_api_version(
            host,
            port=self._http_port,
            httpx_client=get_async_client(self.hass, verify_ssl=False),
        )
        if detection.probe_failed:
            return self.async_abort(reason="cannot_connect")
        self.api_version = detection.api_version

        if self.api_version == "v2":
            if detection.status_info is None:
                return self.async_abort(reason="cannot_connect")
            # v2 reauth: set up flow state manually and offer auth choice
            self.host = host
            self.serial_number = detection.status_info.serial_number
            self.trigger_flow_type = TriggerFlowType.UPDATE_ENTRY
            self._is_flow_setup = True
            return await self.async_step_choose_v2_auth()

        # Non-v2 panels are not supported
        return self.async_abort(reason="v1_not_supported")

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user to confirm a discovered Span Panel."""
        self.ensure_flow_is_set_up()

        # Prompt the user for confirmation
        if user_input is None:
            self._set_confirm_only()
            host = self.host if self.host is not None else ""
            return self.async_show_form(
                step_id="confirm_discovery",
                description_placeholders={
                    "host": host,
                },
            )

        return await self.async_step_choose_v2_auth()

    async def async_step_choose_v2_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose v2 authentication method: passphrase or proximity."""
        return self.async_show_menu(
            step_id="choose_v2_auth",
            menu_options={
                "auth_passphrase": "Enter Panel Passphrase",
                "auth_proximity": "Proof of Proximity (open/close door)",
            },
        )

    async def async_step_auth_proximity(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Instruct user to complete the door challenge, then confirm or switch method."""
        return self.async_show_menu(
            step_id="auth_proximity",
            menu_options={
                "auth_proximity_confirm": "I have opened and closed the door",
                "auth_passphrase": "Use passphrase instead",
            },
        )

    async def async_step_auth_proximity_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Verify proximity was proven, then register."""
        if not self.host:
            return self.async_abort(reason="host_not_set")

        # Check proximityProven before calling register_v2 (avoids 15-min block).
        # On older firmware the field is None — fall through to register_v2 directly.
        detection = await detect_api_version(
            self.host,
            port=self._http_port,
            httpx_client=get_async_client(self.hass, verify_ssl=False),
        )
        proximity_status = (
            detection.status_info.proximity_proven
            if detection.status_info is not None
            else None
        )
        if proximity_status is False:
            # Door challenge not completed — send back to the instruction menu.
            return await self.async_step_auth_proximity()

        try:
            result = await validate_v2_proximity(
                self.hass, self.host, port=self._http_port
            )
        except SpanPanelAuthError, SpanPanelConnectionError:
            return await self.async_step_auth_proximity()

        self._store_v2_auth_result(result, passphrase="")  # nosec B106
        return await self._async_finalize_v2_auth()

    async def async_step_auth_passphrase(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect the panel passphrase for v2 authentication."""
        if user_input is None:
            return self.async_show_form(
                step_id="auth_passphrase",
                data_schema=STEP_AUTH_PASSPHRASE_DATA_SCHEMA,
            )

        passphrase = user_input.get(CONF_HOP_PASSPHRASE, "").strip()
        if not passphrase:
            return self.async_show_form(
                step_id="auth_passphrase",
                data_schema=STEP_AUTH_PASSPHRASE_DATA_SCHEMA,
                errors={"base": "invalid_auth"},
            )

        if not self.host:
            return self.async_abort(reason="host_not_set")

        try:
            result = await validate_v2_passphrase(
                self.hass, self.host, passphrase, port=self._http_port
            )
        except SpanPanelAuthError:
            return self.async_show_form(
                step_id="auth_passphrase",
                data_schema=STEP_AUTH_PASSPHRASE_DATA_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except SpanPanelConnectionError:
            return self.async_show_form(
                step_id="auth_passphrase",
                data_schema=STEP_AUTH_PASSPHRASE_DATA_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        self._store_v2_auth_result(result, passphrase)
        return await self._async_finalize_v2_auth()

    def _store_v2_auth_result(self, result: V2AuthResponse, passphrase: str) -> None:
        """Store v2 auth credentials from registration result."""
        self.access_token = result.access_token
        self._v2_broker_host = result.ebus_broker_host
        self._v2_broker_port = result.ebus_broker_mqtts_port
        self._v2_broker_username = result.ebus_broker_username
        self._v2_broker_password = result.ebus_broker_password
        self._v2_passphrase = passphrase
        self._v2_panel_serial = result.serial_number

    async def _async_finalize_v2_auth(self) -> ConfigFlowResult:
        """Route to appropriate next step after successful v2 auth."""
        if self.trigger_flow_type == TriggerFlowType.UPDATE_ENTRY:
            if "entry_id" not in self.context:
                raise ValueError("Entry ID is missing from context")
            return self._update_v2_entry(self.context["entry_id"])
        # If host is an FQDN, register it with the panel for TLS cert SAN inclusion
        if self.host and is_fqdn(self.host):
            return await self.async_step_register_fqdn()
        return await self.async_step_choose_entity_naming_initial()

    async def async_step_register_fqdn(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Register FQDN with the panel and wait for TLS certificate update."""
        if not self._fqdn_task:
            self._fqdn_task = self.hass.async_create_task(
                self._async_register_fqdn_and_wait(),
                "span_panel_register_fqdn",
            )

        if not self._fqdn_task.done():
            return self.async_show_progress(
                step_id="register_fqdn",
                progress_action="registering_fqdn",
                progress_task=self._fqdn_task,
            )

        try:
            self._fqdn_task.result()
        except Exception:
            _LOGGER.exception("FQDN registration failed for %s", self.host)
            self._fqdn_task = None
            return self.async_show_progress_done(next_step_id="fqdn_failed")

        self._fqdn_task = None
        return self.async_show_progress_done(
            next_step_id="choose_entity_naming_initial"
        )

    async def _async_register_fqdn_and_wait(self) -> None:
        """Register the FQDN and poll until the TLS cert includes it."""
        if not self.host or not self.access_token:
            raise ConfigFlowError(
                "Host and access token required for FQDN registration"
            )

        httpx_client = get_async_client(self.hass, verify_ssl=False)
        await register_fqdn(
            self.host,
            self.access_token,
            self.host,
            port=self._http_port,
            httpx_client=httpx_client,
        )

        mqtts_port = self._v2_broker_port or 8883
        max_attempts = 30
        for attempt in range(max_attempts):
            await asyncio.sleep(2)
            if await check_fqdn_tls_ready(
                self.hass, self.host, mqtts_port, http_port=self._http_port
            ):
                _LOGGER.debug(
                    "FQDN %s found in TLS cert SAN after %d attempts",
                    self.host,
                    attempt + 1,
                )
                return

        raise ConfigFlowError(
            f"Timed out waiting for TLS certificate to include FQDN {self.host}"
        )

    async def async_step_fqdn_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle FQDN registration failure — user may continue without it."""
        if user_input is not None:
            return await self.async_step_choose_entity_naming_initial()
        return self.async_show_form(
            step_id="fqdn_failed",
            data_schema=vol.Schema({}),
            errors={"base": "fqdn_registration_failed"},
        )

    def create_new_entry(
        self, host: str, serial_number: str, access_token: str
    ) -> ConfigFlowResult:
        """Create a new SPAN panel entry."""
        base_name = "Span Panel"
        device_name = self.get_unique_device_name(base_name)
        _LOGGER.debug(
            "CONFIG_FLOW_DEBUG: Creating entry with precision - power: %s, energy: %s",
            self.power_display_precision,
            self.energy_display_precision,
        )
        # Determine initial naming flags with default to Friendly Names
        use_device_prefix = (
            True
            if self._chosen_use_device_prefix is None
            else self._chosen_use_device_prefix
        )
        use_circuit_numbers = (
            False
            if self._chosen_use_circuit_numbers is None
            else self._chosen_use_circuit_numbers
        )

        entry_data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_ACCESS_TOKEN: access_token,
            "device_name": device_name,
            CONF_API_VERSION: "v2",
            CONF_EBUS_BROKER_HOST: self._v2_broker_host,
            CONF_EBUS_BROKER_PORT: self._v2_broker_port,
            CONF_EBUS_BROKER_USERNAME: self._v2_broker_username,
            CONF_EBUS_BROKER_PASSWORD: self._v2_broker_password,
            CONF_HOP_PASSPHRASE: self._v2_passphrase,
            CONF_PANEL_SERIAL: self._v2_panel_serial,
        }

        if self._http_port != 80:
            entry_data[CONF_HTTP_PORT] = self._http_port
        if is_fqdn(host):
            entry_data[CONF_REGISTERED_FQDN] = host

        return self.async_create_entry(
            title=device_name,
            data=entry_data,
            options={
                USE_DEVICE_PREFIX: use_device_prefix,
                USE_CIRCUIT_NUMBERS: use_circuit_numbers,
                POWER_DISPLAY_PRECISION: self.power_display_precision,
                ENERGY_DISPLAY_PRECISION: self.energy_display_precision,
                ENABLE_ENERGY_DIP_COMPENSATION: self._enable_dip_compensation,
            },
        )

    def _update_v2_entry(self, entry_id: str) -> ConfigFlowResult:
        """Update an existing config entry with new v2 MQTT credentials."""
        entry: ConfigEntry[Any] | None = self.hass.config_entries.async_get_entry(
            entry_id
        )
        if entry is None:
            _LOGGER.error("Config entry %s does not exist during v2 reauth", entry_id)
            return self.async_abort(reason="reauth_failed")

        updated_data = dict(entry.data)
        updated_data[CONF_ACCESS_TOKEN] = self.access_token
        updated_data[CONF_API_VERSION] = "v2"
        updated_data[CONF_EBUS_BROKER_HOST] = self._v2_broker_host
        updated_data[CONF_EBUS_BROKER_PORT] = self._v2_broker_port
        updated_data[CONF_EBUS_BROKER_USERNAME] = self._v2_broker_username
        updated_data[CONF_EBUS_BROKER_PASSWORD] = self._v2_broker_password
        updated_data[CONF_HOP_PASSPHRASE] = self._v2_passphrase
        updated_data[CONF_PANEL_SERIAL] = self._v2_panel_serial
        if self._http_port != 80:
            updated_data[CONF_HTTP_PORT] = self._http_port

        self.hass.config_entries.async_update_entry(entry, data=updated_data)
        self.hass.async_create_task(self.hass.config_entries.async_reload(entry_id))
        return self.async_abort(reason="reauth_successful")

    def get_unique_device_name(self, base_name: str) -> str:
        """Return a unique device name based on existing config entry titles."""
        existing_names = {
            entry.title for entry in self.hass.config_entries.async_entries(DOMAIN)
        }
        if base_name not in existing_names:
            return base_name
        i = 2
        while f"{base_name} {i}" in existing_names:
            i += 1
        return f"{base_name} {i}"

    async def async_step_choose_entity_naming_initial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pre-setup choice of Entity ID naming pattern.

        Default to Friendly Names; both choices imply device prefix enabled.
        """

        self.ensure_flow_is_set_up()

        pattern_options = {
            EntityNamingPattern.FRIENDLY_NAMES.value: "Circuit Friendly Names",
            EntityNamingPattern.CIRCUIT_NUMBERS.value: "Tab Based Names",
        }

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(
                        ENTITY_NAMING_PATTERN,
                        default=EntityNamingPattern.FRIENDLY_NAMES.value,
                    ): vol.In(pattern_options)
                }
            )
            return self.async_show_form(
                step_id="choose_entity_naming_initial",
                data_schema=schema,
            )

        selected = user_input.get(
            ENTITY_NAMING_PATTERN, EntityNamingPattern.FRIENDLY_NAMES.value
        )
        self._chosen_use_device_prefix = True
        self._chosen_use_circuit_numbers = (
            selected == EntityNamingPattern.CIRCUIT_NUMBERS.value
        )

        # Proceed to create the entry
        if self.host is None or self.serial_number is None or self.access_token is None:
            raise ConfigFlowError("Missing required parameters during entry creation")
        return self.create_new_entry(self.host, self.serial_number, self.access_token)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration (e.g. host change)."""
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is None:
            current_host = reconfigure_entry.data.get(CONF_HOST, "")
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {vol.Required(CONF_HOST, default=current_host): str}
                ),
            )

        host = user_input[CONF_HOST].strip()
        if not host:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({vol.Required(CONF_HOST, default=""): str}),
                errors={"base": "host_required"},
            )

        # Validate the host is reachable and is a v2 panel
        http_port = int(reconfigure_entry.data.get(CONF_HTTP_PORT, 80))
        try:
            detection = await detect_api_version(
                host,
                port=http_port,
                httpx_client=get_async_client(self.hass, verify_ssl=False),
            )
        except (
            ValueError,
            SpanPanelConnectionError,
            SpanPanelTimeoutError,
            SpanPanelAPIError,
        ):
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
                errors={"base": "cannot_connect"},
            )

        if detection.probe_failed:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
                errors={"base": "cannot_connect"},
            )

        if detection.api_version != "v2" or detection.status_info is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
                errors={"base": "cannot_connect"},
            )

        # Ensure the serial number matches — prevent switching to a different panel
        await self.async_set_unique_id(detection.status_info.serial_number)
        self._abort_if_unique_id_mismatch(reason="unique_id_mismatch")

        if is_fqdn(host):
            # New host is FQDN — register it (replaces any existing FQDN on the panel)
            self.host = host
            self.access_token = str(reconfigure_entry.data.get(CONF_ACCESS_TOKEN, ""))
            self._http_port = http_port
            self._v2_broker_port = int(
                reconfigure_entry.data.get(CONF_EBUS_BROKER_PORT, 8883)
            )
            return await self.async_step_reconfigure_register_fqdn()

        # New host is not an FQDN — simple update
        data_updates: dict[str, Any] = {CONF_HOST: host}
        old_fqdn = str(reconfigure_entry.data.get(CONF_REGISTERED_FQDN, ""))
        if old_fqdn:
            # Switching from FQDN to IP — clean up old registration
            access_token = str(reconfigure_entry.data.get(CONF_ACCESS_TOKEN, ""))
            try:
                await delete_fqdn(
                    host,
                    access_token,
                    port=http_port,
                    httpx_client=get_async_client(self.hass, verify_ssl=False),
                )
            except (
                SpanPanelAPIError,
                SpanPanelAuthError,
                SpanPanelConnectionError,
                SpanPanelTimeoutError,
            ):
                _LOGGER.warning("Failed to delete old FQDN registration: %s", old_fqdn)
            data_updates[CONF_REGISTERED_FQDN] = ""

        return self.async_update_reload_and_abort(
            reconfigure_entry,
            data_updates=data_updates,
        )

    async def async_step_reconfigure_register_fqdn(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Register FQDN during reconfiguration and wait for TLS cert update."""
        if not self._reconfigure_fqdn_task:
            self._reconfigure_fqdn_task = self.hass.async_create_task(
                self._async_register_fqdn_and_wait(),
                "span_panel_reconfigure_fqdn",
            )

        if not self._reconfigure_fqdn_task.done():
            return self.async_show_progress(
                step_id="reconfigure_register_fqdn",
                progress_action="registering_fqdn",
                progress_task=self._reconfigure_fqdn_task,
            )

        try:
            self._reconfigure_fqdn_task.result()
        except Exception:
            _LOGGER.exception(
                "FQDN registration failed during reconfigure for %s", self.host
            )
            self._reconfigure_fqdn_task = None
            return self.async_show_progress_done(next_step_id="reconfigure_fqdn_failed")

        self._reconfigure_fqdn_task = None
        return self.async_show_progress_done(next_step_id="reconfigure_fqdn_done")

    async def async_step_reconfigure_fqdn_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Complete reconfiguration after successful FQDN registration."""
        reconfigure_entry = self._get_reconfigure_entry()
        return self.async_update_reload_and_abort(
            reconfigure_entry,
            data_updates={
                CONF_HOST: self.host or "",
                CONF_REGISTERED_FQDN: self.host or "",
            },
        )

    async def async_step_reconfigure_fqdn_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle FQDN registration failure during reconfigure."""
        if user_input is not None:
            # User chose to continue anyway — update host without FQDN registration
            reconfigure_entry = self._get_reconfigure_entry()
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data_updates={CONF_HOST: self.host or ""},
            )
        return self.async_show_form(
            step_id="reconfigure_fqdn_failed",
            data_schema=vol.Schema({}),
            errors={"base": "fqdn_registration_failed"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SpanPanelConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()


OPTIONS_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Optional(SNAPSHOT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=15)
        ),
        vol.Optional(ENTITY_NAMING_PATTERN): vol.In(
            [e.value for e in EntityNamingPattern]
        ),
        vol.Optional(ENERGY_REPORTING_GRACE_PERIOD): vol.All(
            int, vol.Range(min=0, max=60)
        ),
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the options flow for Span Panel."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the options flow with general options directly."""
        return await self.async_step_general_options(user_input)

    async def async_step_general_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the general options (excluding entity naming)."""
        if user_input is not None:
            # Process the user input using the utility function
            filtered_input, errors = process_general_options_input(
                self.config_entry, user_input
            )

            # If no errors, proceed with saving options
            if not errors:
                return self.async_create_entry(title="", data=filtered_input)
        else:
            errors = {}

        # Build schema and defaults using utility functions
        schema = build_general_options_schema(self.config_entry)
        defaults = get_general_options_defaults(self.config_entry)

        return self.async_show_form(
            step_id="general_options",
            data_schema=self.add_suggested_values_to_schema(schema, defaults),
            errors=errors,
        )


# Register the config flow handler
config_entries.HANDLERS.register(DOMAIN)(SpanPanelConfigFlow)
