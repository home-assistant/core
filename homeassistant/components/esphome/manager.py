"""Manager for esphome devices."""

from __future__ import annotations

import asyncio
from functools import partial
import logging
import re
from typing import TYPE_CHECKING, Any, NamedTuple

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    APIVersion,
    DeviceInfo as EsphomeDeviceInfo,
    EncryptionPlaintextAPIError,
    EntityInfo,
    HomeassistantServiceCall,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    LogLevel,
    ReconnectLogic,
    RequiresEncryptionAPIError,
    UserService,
    UserServiceArgType,
)
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.components import bluetooth, tag, zeroconf
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_MODE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_LOGGING_CHANGED,
    Platform,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
    template,
)
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.template import Template
from homeassistant.util.async_ import create_eager_task

from .bluetooth import async_connect_scanner
from .const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_BLUETOOTH_MAC_ADDRESS,
    CONF_DEVICE_NAME,
    CONF_SUBSCRIBE_LOGS,
    DEFAULT_ALLOW_SERVICE_CALLS,
    DEFAULT_URL,
    DOMAIN,
    PROJECT_URLS,
    STABLE_BLE_VERSION,
    STABLE_BLE_VERSION_STR,
)
from .dashboard import async_get_dashboard
from .domain_data import DomainData

# Import config flow so that it's added to the registry
from .entry_data import ESPHomeConfigEntry, RuntimeEntryData

DEVICE_CONFLICT_ISSUE_FORMAT = "device_conflict-{}"

if TYPE_CHECKING:
    from aioesphomeapi.api_pb2 import (  # type: ignore[attr-defined]
        SubscribeLogsResponse,
    )


_LOGGER = logging.getLogger(__name__)

LOG_LEVEL_TO_LOGGER = {
    LogLevel.LOG_LEVEL_NONE: logging.DEBUG,
    LogLevel.LOG_LEVEL_ERROR: logging.ERROR,
    LogLevel.LOG_LEVEL_WARN: logging.WARNING,
    LogLevel.LOG_LEVEL_INFO: logging.INFO,
    LogLevel.LOG_LEVEL_CONFIG: logging.INFO,
    LogLevel.LOG_LEVEL_DEBUG: logging.DEBUG,
    LogLevel.LOG_LEVEL_VERBOSE: logging.DEBUG,
    LogLevel.LOG_LEVEL_VERY_VERBOSE: logging.DEBUG,
}
LOGGER_TO_LOG_LEVEL = {
    logging.NOTSET: LogLevel.LOG_LEVEL_VERY_VERBOSE,
    logging.DEBUG: LogLevel.LOG_LEVEL_VERY_VERBOSE,
    logging.INFO: LogLevel.LOG_LEVEL_CONFIG,
    logging.WARNING: LogLevel.LOG_LEVEL_WARN,
    logging.ERROR: LogLevel.LOG_LEVEL_ERROR,
    logging.CRITICAL: LogLevel.LOG_LEVEL_ERROR,
}
# 7-bit and 8-bit C1 ANSI sequences
# https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python
ANSI_ESCAPE_78BIT = re.compile(
    rb"(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])"
)


@callback
def _async_check_firmware_version(
    hass: HomeAssistant, device_info: EsphomeDeviceInfo, api_version: APIVersion
) -> None:
    """Create or delete an the ble_firmware_outdated issue."""
    # ESPHome device_info.mac_address is the unique_id
    issue = f"ble_firmware_outdated-{device_info.mac_address}"
    if (
        not device_info.bluetooth_proxy_feature_flags_compat(api_version)
        # If the device has a project name its up to that project
        # to tell them about the firmware version update so we don't notify here
        or (device_info.project_name and device_info.project_name not in PROJECT_URLS)
        or AwesomeVersion(device_info.esphome_version) >= STABLE_BLE_VERSION
    ):
        async_delete_issue(hass, DOMAIN, issue)
        return
    async_create_issue(
        hass,
        DOMAIN,
        issue,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        learn_more_url=PROJECT_URLS.get(device_info.project_name, DEFAULT_URL),
        translation_key="ble_firmware_outdated",
        translation_placeholders={
            "name": device_info.name,
            "version": STABLE_BLE_VERSION_STR,
        },
    )


@callback
def _async_check_using_api_password(
    hass: HomeAssistant, device_info: EsphomeDeviceInfo, has_password: bool
) -> None:
    """Create or delete an the api_password_deprecated issue."""
    # ESPHome device_info.mac_address is the unique_id
    issue = f"api_password_deprecated-{device_info.mac_address}"
    if not has_password:
        async_delete_issue(hass, DOMAIN, issue)
        return
    async_create_issue(
        hass,
        DOMAIN,
        issue,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        learn_more_url="https://esphome.io/components/api.html",
        translation_key="api_password_deprecated",
        translation_placeholders={
            "name": device_info.name,
        },
    )


class ESPHomeManager:
    """Class to manage an ESPHome connection."""

    __slots__ = (
        "_cancel_subscribe_logs",
        "_log_level",
        "cli",
        "device_id",
        "domain_data",
        "entry",
        "entry_data",
        "hass",
        "host",
        "password",
        "reconnect_logic",
        "zeroconf_instance",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ESPHomeConfigEntry,
        host: str,
        password: str | None,
        cli: APIClient,
        zeroconf_instance: zeroconf.HaZeroconf,
        domain_data: DomainData,
    ) -> None:
        """Initialize the esphome manager."""
        self.hass = hass
        self.host = host
        self.password = password
        self.entry = entry
        self.cli = cli
        self.device_id: str | None = None
        self.domain_data = domain_data
        self.reconnect_logic: ReconnectLogic | None = None
        self.zeroconf_instance = zeroconf_instance
        self.entry_data = entry.runtime_data
        self._cancel_subscribe_logs: CALLBACK_TYPE | None = None
        self._log_level = LogLevel.LOG_LEVEL_NONE

    async def on_stop(self, event: Event) -> None:
        """Cleanup the socket client on HA close."""
        await cleanup_instance(self.entry)

    @property
    def services_issue(self) -> str:
        """Return the services issue name for this entry."""
        return f"service_calls_not_enabled-{self.entry.unique_id}"

    @callback
    def async_on_service_call(self, service: HomeassistantServiceCall) -> None:
        """Call service when user automation in ESPHome config is triggered."""
        hass = self.hass
        domain, service_name = service.service.split(".", 1)
        service_data = service.data

        if service.data_template:
            try:
                data_template = {
                    key: Template(value, hass)
                    for key, value in service.data_template.items()
                }
                service_data.update(
                    template.render_complex(data_template, service.variables)
                )
            except TemplateError as ex:
                _LOGGER.error(
                    "Error rendering data template %s for %s: %s",
                    service.data_template,
                    self.host,
                    ex,
                )
                return

        if service.is_event:
            device_id = self.device_id
            # ESPHome uses service call packet for both events and service calls
            # Ensure the user can only send events of form 'esphome.xyz'
            if domain != DOMAIN:
                _LOGGER.error(
                    "Can only generate events under esphome domain! (%s)", self.host
                )
                return

            # Call native tag scan
            if service_name == "tag_scanned" and device_id is not None:
                tag_id = service_data["tag_id"]
                hass.async_create_task(tag.async_scan_tag(hass, tag_id, device_id))
                return

            hass.bus.async_fire(
                service.service,
                {
                    ATTR_DEVICE_ID: device_id,
                    **service_data,
                },
            )
        elif self.entry.options.get(
            CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS
        ):
            hass.async_create_task(
                hass.services.async_call(
                    domain, service_name, service_data, blocking=True
                )
            )
        else:
            device_info = self.entry_data.device_info
            assert device_info is not None
            async_create_issue(
                hass,
                DOMAIN,
                self.services_issue,
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="service_calls_not_allowed",
                translation_placeholders={
                    "name": device_info.friendly_name or device_info.name,
                },
            )
            _LOGGER.error(
                "%s: Service call %s.%s: with data %s rejected; "
                "If you trust this device and want to allow access for it to make "
                "Home Assistant service calls, you can enable this "
                "functionality in the options flow",
                device_info.friendly_name or device_info.name,
                domain,
                service_name,
                service_data,
            )

    @callback
    def _send_home_assistant_state(
        self, entity_id: str, attribute: str | None, state: State | None
    ) -> None:
        """Forward Home Assistant states to ESPHome."""
        if state is None or (attribute and attribute not in state.attributes):
            return

        send_state = state.state
        if attribute:
            attr_val = state.attributes[attribute]
            # ESPHome only handles "on"/"off" for boolean values
            if isinstance(attr_val, bool):
                send_state = "on" if attr_val else "off"
            else:
                send_state = attr_val

        self.cli.send_home_assistant_state(entity_id, attribute, str(send_state))

    @callback
    def _send_home_assistant_state_event(
        self,
        attribute: str | None,
        event: Event[EventStateChangedData],
    ) -> None:
        """Forward Home Assistant states updates to ESPHome."""
        event_data = event.data
        new_state = event_data["new_state"]
        old_state = event_data["old_state"]

        if new_state is None or old_state is None:
            return

        # Only communicate changes to the state or attribute tracked
        if (not attribute and old_state.state == new_state.state) or (
            attribute
            and old_state.attributes.get(attribute)
            == new_state.attributes.get(attribute)
        ):
            return

        self._send_home_assistant_state(event.data["entity_id"], attribute, new_state)

    @callback
    def async_on_state_subscription(
        self, entity_id: str, attribute: str | None = None
    ) -> None:
        """Subscribe and forward states for requested entities."""
        hass = self.hass
        self.entry_data.disconnect_callbacks.add(
            async_track_state_change_event(
                hass,
                [entity_id],
                partial(self._send_home_assistant_state_event, attribute),
            )
        )
        # Send initial state
        self._send_home_assistant_state(
            entity_id, attribute, hass.states.get(entity_id)
        )

    @callback
    def async_on_state_request(
        self, entity_id: str, attribute: str | None = None
    ) -> None:
        """Forward state for requested entity."""
        self._send_home_assistant_state(
            entity_id, attribute, self.hass.states.get(entity_id)
        )

    async def on_connect(self) -> None:
        """Subscribe to states and list entities on successful API login."""
        try:
            await self._on_connect()
        except APIConnectionError as err:
            _LOGGER.warning(
                "Error getting setting up connection for %s: %s", self.host, err
            )
            # Re-connection logic will trigger after this
            await self.cli.disconnect()

    def _async_on_log(self, msg: SubscribeLogsResponse) -> None:
        """Handle a log message from the API."""
        log: bytes = msg.message
        _LOGGER.log(
            LOG_LEVEL_TO_LOGGER.get(msg.level, logging.DEBUG),
            "%s: %s",
            self.entry.title,
            ANSI_ESCAPE_78BIT.sub(b"", log).decode("utf-8", "backslashreplace"),
        )

    @callback
    def _async_get_equivalent_log_level(self) -> LogLevel:
        """Get the equivalent ESPHome log level for the current logger."""
        return LOGGER_TO_LOG_LEVEL.get(
            _LOGGER.getEffectiveLevel(), LogLevel.LOG_LEVEL_VERY_VERBOSE
        )

    @callback
    def _async_subscribe_logs(self, log_level: LogLevel) -> None:
        """Subscribe to logs."""
        if self._cancel_subscribe_logs is not None:
            self._cancel_subscribe_logs()
            self._cancel_subscribe_logs = None
        self._log_level = log_level
        self._cancel_subscribe_logs = self.cli.subscribe_logs(
            self._async_on_log, self._log_level
        )

    async def _on_connect(self) -> None:
        """Subscribe to states and list entities on successful API login."""
        entry = self.entry
        unique_id = entry.unique_id
        entry_data = self.entry_data
        reconnect_logic = self.reconnect_logic
        assert reconnect_logic is not None, "Reconnect logic must be set"
        hass = self.hass
        cli = self.cli
        stored_device_name: str | None = entry.data.get(CONF_DEVICE_NAME)
        unique_id_is_mac_address = unique_id and ":" in unique_id
        if entry.options.get(CONF_SUBSCRIBE_LOGS):
            self._async_subscribe_logs(self._async_get_equivalent_log_level())
        results = await asyncio.gather(
            create_eager_task(cli.device_info()),
            create_eager_task(cli.list_entities_services()),
        )

        device_info: EsphomeDeviceInfo = results[0]
        entity_infos_services: tuple[list[EntityInfo], list[UserService]] = results[1]
        entity_infos, services = entity_infos_services

        device_mac = format_mac(device_info.mac_address)
        mac_address_matches = unique_id == device_mac
        if (
            bluetooth_mac_address := device_info.bluetooth_mac_address
        ) and entry.data.get(CONF_BLUETOOTH_MAC_ADDRESS) != bluetooth_mac_address:
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_BLUETOOTH_MAC_ADDRESS: bluetooth_mac_address},
            )
        #
        # Migrate config entry to new unique ID if the current
        # unique id is not a mac address.
        #
        # This was changed in 2023.1
        if not mac_address_matches and not unique_id_is_mac_address:
            hass.config_entries.async_update_entry(entry, unique_id=device_mac)

        issue = DEVICE_CONFLICT_ISSUE_FORMAT.format(entry.entry_id)
        if not mac_address_matches and unique_id_is_mac_address:
            # If the unique id is a mac address
            # and does not match we have the wrong device and we need
            # to abort the connection. This can happen if the DHCP
            # server changes the IP address of the device and we end up
            # connecting to the wrong device.
            if stored_device_name == device_info.name:
                # If the device name matches it might be a device replacement
                # or they made a mistake and flashed the same firmware on
                # multiple devices. In this case we start a repair flow
                # to ask them if its a mistake, or if they want to migrate
                # the config entry to the replacement hardware.
                shared_data = {
                    "name": device_info.name,
                    "mac": format_mac(device_mac),
                    "stored_mac": format_mac(unique_id),
                    "model": device_info.model,
                    "ip": self.host,
                }
                async_create_issue(
                    hass,
                    DOMAIN,
                    issue,
                    is_fixable=True,
                    severity=IssueSeverity.ERROR,
                    translation_key="device_conflict",
                    translation_placeholders=shared_data,
                    data={**shared_data, "entry_id": entry.entry_id},
                )
            _LOGGER.error(
                "Unexpected device found at %s; "
                "expected `%s` with mac address `%s`, "
                "found `%s` with mac address `%s`",
                self.host,
                stored_device_name,
                unique_id,
                device_info.name,
                device_mac,
            )
            await cli.disconnect()
            await reconnect_logic.stop()
            # We don't want to reconnect to the wrong device
            # so we stop the reconnect logic and disconnect
            # the client. When discovery finds the new IP address
            # for the device, the config entry will be updated
            # and we will connect to the correct device when
            # the config entry gets reloaded by the discovery
            # flow.
            return

        async_delete_issue(hass, DOMAIN, issue)
        # Make sure we have the correct device name stored
        # so we can map the device to ESPHome Dashboard config
        # If we got here, we know the mac address matches or we
        # did a migration to the mac address so we can update
        # the device name.
        if stored_device_name != device_info.name:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_DEVICE_NAME: device_info.name}
            )

        api_version = cli.api_version
        assert api_version is not None, "API version must be set"
        entry_data.async_on_connect(device_info, api_version)

        if device_info.name:
            reconnect_logic.name = device_info.name

        if not device_info.friendly_name:
            _LOGGER.info(
                "No `friendly_name` set in the `esphome:` section of the "
                "YAML config for device '%s' (MAC: %s); It's recommended "
                "to add one for easier identification and better alignment "
                "with Home Assistant naming conventions",
                device_info.name,
                device_mac,
            )
        self.device_id = _async_setup_device_registry(hass, entry, entry_data)

        entry_data.async_update_device_state()
        await entry_data.async_update_static_infos(
            hass, entry, entity_infos, device_info.mac_address
        )
        _setup_services(hass, entry_data, services)

        if device_info.bluetooth_proxy_feature_flags_compat(api_version):
            entry_data.disconnect_callbacks.add(
                async_connect_scanner(
                    hass, entry_data, cli, device_info, self.device_id
                )
            )
        else:
            bluetooth.async_remove_scanner(
                hass, device_info.bluetooth_mac_address or device_info.mac_address
            )

        if device_info.voice_assistant_feature_flags_compat(api_version) and (
            Platform.ASSIST_SATELLITE not in entry_data.loaded_platforms
        ):
            # Create assist satellite entity
            await self.hass.config_entries.async_forward_entry_setups(
                self.entry, [Platform.ASSIST_SATELLITE]
            )
            entry_data.loaded_platforms.add(Platform.ASSIST_SATELLITE)

        cli.subscribe_states(entry_data.async_update_state)
        cli.subscribe_service_calls(self.async_on_service_call)
        cli.subscribe_home_assistant_states(
            self.async_on_state_subscription,
            self.async_on_state_request,
        )

        entry_data.async_save_to_store()
        _async_check_firmware_version(hass, device_info, api_version)
        _async_check_using_api_password(hass, device_info, bool(self.password))

    async def on_disconnect(self, expected_disconnect: bool) -> None:
        """Run disconnect callbacks on API disconnect."""
        entry_data = self.entry_data
        hass = self.hass
        host = self.host
        name = entry_data.device_info.name if entry_data.device_info else host
        _LOGGER.debug(
            "%s: %s disconnected (expected=%s), running disconnected callbacks",
            name,
            host,
            expected_disconnect,
        )
        entry_data.async_on_disconnect()
        entry_data.expected_disconnect = expected_disconnect
        # Mark state as stale so that we will always dispatch
        # the next state update of that type when the device reconnects
        entry_data.stale_state = {
            (type(entity_state), key)
            for state_dict in entry_data.state.values()
            for key, entity_state in state_dict.items()
        }
        if not hass.is_stopping:
            # Avoid marking every esphome entity as unavailable on shutdown
            # since it generates a lot of state changed events and database
            # writes when we already know we're shutting down and the state
            # will be cleared anyway.
            entry_data.async_update_device_state()

        if Platform.ASSIST_SATELLITE in self.entry_data.loaded_platforms:
            await self.hass.config_entries.async_unload_platforms(
                self.entry, [Platform.ASSIST_SATELLITE]
            )

            self.entry_data.loaded_platforms.remove(Platform.ASSIST_SATELLITE)

    async def on_connect_error(self, err: Exception) -> None:
        """Start reauth flow if appropriate connect error type."""
        if not isinstance(
            err,
            (
                EncryptionPlaintextAPIError,
                RequiresEncryptionAPIError,
                InvalidEncryptionKeyAPIError,
                InvalidAuthAPIError,
            ),
        ):
            return
        if isinstance(err, InvalidEncryptionKeyAPIError):
            if (
                (received_name := err.received_name)
                and (received_mac := err.received_mac)
                and (unique_id := self.entry.unique_id)
                and ":" in unique_id
            ):
                formatted_received_mac = format_mac(received_mac)
                formatted_expected_mac = format_mac(unique_id)
                if formatted_received_mac != formatted_expected_mac:
                    _LOGGER.error(
                        "Unexpected device found at %s; "
                        "expected `%s` with mac address `%s`, "
                        "found `%s` with mac address `%s`",
                        self.host,
                        self.entry.data.get(CONF_DEVICE_NAME),
                        formatted_expected_mac,
                        received_name,
                        formatted_received_mac,
                    )
                    # If the device comes back online, discovery
                    # will update the config entry with the new IP address
                    # and reload which will try again to connect to the device.
                    # In the mean time we stop the reconnect logic
                    # so we don't keep trying to connect to the wrong device.
                    if self.reconnect_logic:
                        await self.reconnect_logic.stop()
                    return
        self.entry.async_start_reauth(self.hass)

    @callback
    def _async_handle_logging_changed(self, _event: Event) -> None:
        """Handle when the logging level changes."""
        self.cli.set_debug(_LOGGER.isEnabledFor(logging.DEBUG))
        if self.entry.options.get(CONF_SUBSCRIBE_LOGS) and self._log_level != (
            new_log_level := self._async_get_equivalent_log_level()
        ):
            self._async_subscribe_logs(new_log_level)

    @callback
    def _async_cleanup(self) -> None:
        """Cleanup stale issues and entities."""
        assert self.entry_data.device_info is not None
        ent_reg = er.async_get(self.hass)
        # Cleanup stale assist_in_progress entity and issue,
        # Remove this after 2026.4
        if not (
            stale_entry_entity_id := ent_reg.async_get_entity_id(
                DOMAIN,
                Platform.BINARY_SENSOR,
                f"{self.entry_data.device_info.mac_address}-assist_in_progress",
            )
        ):
            return
        stale_entry = ent_reg.async_get(stale_entry_entity_id)
        assert stale_entry is not None
        ent_reg.async_remove(stale_entry_entity_id)
        issue_reg = ir.async_get(self.hass)
        if issue := issue_reg.async_get_issue(
            DOMAIN, f"assist_in_progress_deprecated_{stale_entry.id}"
        ):
            issue_reg.async_delete(DOMAIN, issue.issue_id)

    async def async_start(self) -> None:
        """Start the esphome connection manager."""
        hass = self.hass
        entry = self.entry
        entry_data = self.entry_data

        if entry.options.get(CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS):
            async_delete_issue(hass, DOMAIN, self.services_issue)

        reconnect_logic = ReconnectLogic(
            client=self.cli,
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect,
            zeroconf_instance=self.zeroconf_instance,
            name=entry.data.get(CONF_DEVICE_NAME, self.host),
            on_connect_error=self.on_connect_error,
        )
        self.reconnect_logic = reconnect_logic

        # Use async_listen instead of async_listen_once so that we don't deregister
        # the callback twice when shutting down Home Assistant.
        # "Unable to remove unknown listener
        # <function EventBus.async_listen_once.<locals>.onetime_listener>"
        # We only close the connection at the last possible moment
        # when the CLOSE event is fired so anything using a Bluetooth
        # proxy has a chance to shut down properly.
        bus = hass.bus
        cleanups = (
            bus.async_listen(EVENT_HOMEASSISTANT_CLOSE, self.on_stop),
            bus.async_listen(EVENT_LOGGING_CHANGED, self._async_handle_logging_changed),
            reconnect_logic.stop_callback,
        )
        entry_data.cleanup_callbacks.extend(cleanups)

        infos, services = await entry_data.async_load_from_store()
        if entry.unique_id:
            await entry_data.async_update_static_infos(
                hass, entry, infos, entry.unique_id.upper()
            )
        _setup_services(hass, entry_data, services)

        if (device_info := entry_data.device_info) is not None:
            self._async_cleanup()
            if device_info.name:
                reconnect_logic.name = device_info.name
            if (
                bluetooth_mac_address := device_info.bluetooth_mac_address
            ) and entry.data.get(CONF_BLUETOOTH_MAC_ADDRESS) != bluetooth_mac_address:
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_BLUETOOTH_MAC_ADDRESS: bluetooth_mac_address,
                    },
                )
            if entry.unique_id is None:
                hass.config_entries.async_update_entry(
                    entry, unique_id=format_mac(device_info.mac_address)
                )

        await reconnect_logic.start()

        entry.async_on_unload(
            entry.add_update_listener(entry_data.async_update_listener)
        )


@callback
def _async_setup_device_registry(
    hass: HomeAssistant, entry: ESPHomeConfigEntry, entry_data: RuntimeEntryData
) -> str:
    """Set up device registry feature for a particular config entry."""
    device_info = entry_data.device_info
    if TYPE_CHECKING:
        assert device_info is not None
    sw_version = device_info.esphome_version
    if device_info.compilation_time:
        sw_version += f" ({device_info.compilation_time})"

    configuration_url = None
    if device_info.webserver_port > 0:
        entry_host = entry.data["host"]
        host = f"[{entry_host}]" if ":" in entry_host else entry_host
        configuration_url = f"http://{host}:{device_info.webserver_port}"
    elif (
        (dashboard := async_get_dashboard(hass))
        and dashboard.data
        and dashboard.data.get(device_info.name)
    ):
        configuration_url = f"homeassistant://hassio/ingress/{dashboard.addon_slug}"

    manufacturer = "espressif"
    if device_info.manufacturer:
        manufacturer = device_info.manufacturer
    model = device_info.model
    if device_info.project_name:
        project_name = device_info.project_name.split(".")
        manufacturer = project_name[0]
        model = project_name[1]
        sw_version = (
            f"{device_info.project_version} (ESPHome {device_info.esphome_version})"
        )

    suggested_area = None
    if device_info.suggested_area:
        suggested_area = device_info.suggested_area

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        configuration_url=configuration_url,
        connections={(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)},
        name=entry_data.friendly_name or entry_data.name,
        manufacturer=manufacturer,
        model=model,
        sw_version=sw_version,
        suggested_area=suggested_area,
    )
    return device_entry.id


class ServiceMetadata(NamedTuple):
    """Metadata for services."""

    validator: Any
    example: str
    selector: dict[str, Any]
    description: str | None = None


ARG_TYPE_METADATA = {
    UserServiceArgType.BOOL: ServiceMetadata(
        validator=cv.boolean,
        example="False",
        selector={"boolean": None},
    ),
    UserServiceArgType.INT: ServiceMetadata(
        validator=vol.Coerce(int),
        example="42",
        selector={"number": {CONF_MODE: "box"}},
    ),
    UserServiceArgType.FLOAT: ServiceMetadata(
        validator=vol.Coerce(float),
        example="12.3",
        selector={"number": {CONF_MODE: "box", "step": 1e-3}},
    ),
    UserServiceArgType.STRING: ServiceMetadata(
        validator=cv.string,
        example="Example text",
        selector={"text": None},
    ),
    UserServiceArgType.BOOL_ARRAY: ServiceMetadata(
        validator=[cv.boolean],
        description="A list of boolean values.",
        example="[True, False]",
        selector={"object": {}},
    ),
    UserServiceArgType.INT_ARRAY: ServiceMetadata(
        validator=[vol.Coerce(int)],
        description="A list of integer values.",
        example="[42, 34]",
        selector={"object": {}},
    ),
    UserServiceArgType.FLOAT_ARRAY: ServiceMetadata(
        validator=[vol.Coerce(float)],
        description="A list of floating point numbers.",
        example="[ 12.3, 34.5 ]",
        selector={"object": {}},
    ),
    UserServiceArgType.STRING_ARRAY: ServiceMetadata(
        validator=[cv.string],
        description="A list of strings.",
        example="['Example text', 'Another example']",
        selector={"object": {}},
    ),
}


@callback
def execute_service(
    entry_data: RuntimeEntryData, service: UserService, call: ServiceCall
) -> None:
    """Execute a service on a node."""
    try:
        entry_data.client.execute_service(service, call.data)
    except APIConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_call_failed",
            translation_placeholders={
                "call_name": service.name,
                "device_name": entry_data.name,
                "error": str(err),
            },
        ) from err


def build_service_name(device_info: EsphomeDeviceInfo, service: UserService) -> str:
    """Build a service name for a node."""
    return f"{device_info.name.replace('-', '_')}_{service.name}"


@callback
def _async_register_service(
    hass: HomeAssistant,
    entry_data: RuntimeEntryData,
    device_info: EsphomeDeviceInfo,
    service: UserService,
) -> None:
    """Register a service on a node."""
    service_name = build_service_name(device_info, service)
    schema = {}
    fields = {}

    for arg in service.args:
        if arg.type not in ARG_TYPE_METADATA:
            _LOGGER.error(
                "Can't register service %s because %s is of unknown type %s",
                service_name,
                arg.name,
                arg.type,
            )
            return
        metadata = ARG_TYPE_METADATA[arg.type]
        schema[vol.Required(arg.name)] = metadata.validator
        fields[arg.name] = {
            "name": arg.name,
            "required": True,
            "description": metadata.description,
            "example": metadata.example,
            "selector": metadata.selector,
        }

    hass.services.async_register(
        DOMAIN,
        service_name,
        partial(execute_service, entry_data, service),
        vol.Schema(schema),
    )
    async_set_service_schema(
        hass,
        DOMAIN,
        service_name,
        {
            "description": (
                f"Calls the service {service.name} of the node {device_info.name}"
            ),
            "fields": fields,
        },
    )


@callback
def _setup_services(
    hass: HomeAssistant, entry_data: RuntimeEntryData, services: list[UserService]
) -> None:
    device_info = entry_data.device_info
    if device_info is None:
        # Can happen if device has never connected or .storage cleared
        return
    old_services = entry_data.services.copy()
    to_unregister: list[UserService] = []
    to_register: list[UserService] = []
    for service in services:
        if service.key in old_services:
            # Already exists
            if (matching := old_services.pop(service.key)) != service:
                # Need to re-register
                to_unregister.append(matching)
                to_register.append(service)
        else:
            # New service
            to_register.append(service)

    to_unregister.extend(old_services.values())

    entry_data.services = {serv.key: serv for serv in services}

    for service in to_unregister:
        service_name = build_service_name(device_info, service)
        hass.services.async_remove(DOMAIN, service_name)

    for service in to_register:
        _async_register_service(hass, entry_data, device_info, service)


async def cleanup_instance(entry: ESPHomeConfigEntry) -> RuntimeEntryData:
    """Cleanup the esphome client if it exists."""
    data = entry.runtime_data
    data.async_on_disconnect()
    for cleanup_callback in data.cleanup_callbacks:
        cleanup_callback()
    await data.async_cleanup()
    await data.client.disconnect()
    return data


async def async_replace_device(
    hass: HomeAssistant,
    entry_id: str,
    old_mac: str,  # will be lower case (format_mac)
    new_mac: str,  # will be lower case (format_mac)
) -> None:
    """Migrate an ESPHome entry to replace an existing device."""
    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry is not None
    hass.config_entries.async_update_entry(entry, unique_id=new_mac)

    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        dev_reg.async_update_device(
            device.id,
            new_connections={(dr.CONNECTION_NETWORK_MAC, new_mac)},
        )

    ent_reg = er.async_get(hass)
    upper_mac = new_mac.upper()
    old_upper_mac = old_mac.upper()
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        # <upper_mac>-<entity type>-<object_id>
        old_unique_id = entity.unique_id.split("-")
        new_unique_id = "-".join([upper_mac, *old_unique_id[1:]])
        if entity.unique_id != new_unique_id and entity.unique_id.startswith(
            old_upper_mac
        ):
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)

    domain_data = DomainData.get(hass)
    store = domain_data.get_or_create_store(hass, entry)
    if data := await store.async_load():
        data["device_info"]["mac_address"] = upper_mac
        await store.async_save(data)
