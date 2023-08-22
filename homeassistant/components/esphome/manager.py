"""Manager for esphome devices."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    APIVersion,
    DeviceInfo as EsphomeDeviceInfo,
    HomeassistantServiceCall,
    InvalidAuthAPIError,
    InvalidEncryptionKeyAPIError,
    ReconnectLogic,
    RequiresEncryptionAPIError,
    UserService,
    UserServiceArgType,
    VoiceAssistantEventType,
)
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.components import tag, zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_MODE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, ServiceCall, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import EventType

from .bluetooth import async_connect_scanner
from .const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_DEVICE_NAME,
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
from .entry_data import RuntimeEntryData
from .voice_assistant import VoiceAssistantUDPServer

_LOGGER = logging.getLogger(__name__)


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
        "hass",
        "host",
        "password",
        "entry",
        "cli",
        "device_id",
        "domain_data",
        "voice_assistant_udp_server",
        "reconnect_logic",
        "zeroconf_instance",
        "entry_data",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
        password: str | None,
        cli: APIClient,
        zeroconf_instance: zeroconf.HaZeroconf,
        domain_data: DomainData,
        entry_data: RuntimeEntryData,
    ) -> None:
        """Initialize the esphome manager."""
        self.hass = hass
        self.host = host
        self.password = password
        self.entry = entry
        self.cli = cli
        self.device_id: str | None = None
        self.domain_data = domain_data
        self.voice_assistant_udp_server: VoiceAssistantUDPServer | None = None
        self.reconnect_logic: ReconnectLogic | None = None
        self.zeroconf_instance = zeroconf_instance
        self.entry_data = entry_data

    async def on_stop(self, event: Event) -> None:
        """Cleanup the socket client on HA stop."""
        await cleanup_instance(self.hass, self.entry)

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
                    key: Template(value) for key, value in service.data_template.items()
                }
                template.attach(hass, data_template)
                service_data.update(
                    template.render_complex(data_template, service.variables)
                )
            except TemplateError as ex:
                _LOGGER.error("Error rendering data template for %s: %s", self.host, ex)
                return

        if service.is_event:
            device_id = self.device_id
            # ESPHome uses service call packet for both events and service calls
            # Ensure the user can only send events of form 'esphome.xyz'
            if domain != "esphome":
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

    async def _send_home_assistant_state(
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

        await self.cli.send_home_assistant_state(entity_id, attribute, str(send_state))

    @callback
    def async_on_state_subscription(
        self, entity_id: str, attribute: str | None = None
    ) -> None:
        """Subscribe and forward states for requested entities."""
        hass = self.hass

        async def send_home_assistant_state_event(
            event: EventType[EventStateChangedData],
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

            await self._send_home_assistant_state(
                event.data["entity_id"], attribute, new_state
            )

        self.entry_data.disconnect_callbacks.append(
            async_track_state_change_event(
                hass, [entity_id], send_home_assistant_state_event
            )
        )

        # Send initial state
        hass.async_create_task(
            self._send_home_assistant_state(
                entity_id, attribute, hass.states.get(entity_id)
            )
        )

    def _handle_pipeline_event(
        self, event_type: VoiceAssistantEventType, data: dict[str, str] | None
    ) -> None:
        self.cli.send_voice_assistant_event(event_type, data)

    def _handle_pipeline_finished(self) -> None:
        self.entry_data.async_set_assist_pipeline_state(False)

        if self.voice_assistant_udp_server is not None:
            self.voice_assistant_udp_server.close()
            self.voice_assistant_udp_server = None

    async def _handle_pipeline_start(
        self, conversation_id: str, flags: int
    ) -> int | None:
        """Start a voice assistant pipeline."""
        if self.voice_assistant_udp_server is not None:
            return None

        hass = self.hass
        voice_assistant_udp_server = VoiceAssistantUDPServer(
            hass,
            self.entry_data,
            self._handle_pipeline_event,
            self._handle_pipeline_finished,
        )
        port = await voice_assistant_udp_server.start_server()

        assert self.device_id is not None, "Device ID must be set"
        hass.async_create_background_task(
            voice_assistant_udp_server.run_pipeline(
                device_id=self.device_id,
                conversation_id=conversation_id or None,
                flags=flags,
            ),
            "esphome.voice_assistant_udp_server.run_pipeline",
        )
        self.entry_data.async_set_assist_pipeline_state(True)

        return port

    async def _handle_pipeline_stop(self) -> None:
        """Stop a voice assistant pipeline."""
        if self.voice_assistant_udp_server is not None:
            self.voice_assistant_udp_server.stop()

    async def on_connect(self) -> None:
        """Subscribe to states and list entities on successful API login."""
        entry = self.entry
        unique_id = entry.unique_id
        entry_data = self.entry_data
        reconnect_logic = self.reconnect_logic
        assert reconnect_logic is not None, "Reconnect logic must be set"
        hass = self.hass
        cli = self.cli
        stored_device_name = entry.data.get(CONF_DEVICE_NAME)
        unique_id_is_mac_address = unique_id and ":" in unique_id
        try:
            device_info = await cli.device_info()
        except APIConnectionError as err:
            _LOGGER.warning("Error getting device info for %s: %s", self.host, err)
            # Re-connection logic will trigger after this
            await cli.disconnect()
            return

        device_mac = format_mac(device_info.mac_address)
        mac_address_matches = unique_id == device_mac
        name_matches = stored_device_name == device_info.name
        #
        # Migrate config entry to new unique ID if the current
        # unique id is not a mac address.
        #
        # This was changed in 2023.1
        #
        # If the device name matches, we also update the unique id
        # to the mac address. This is to handle a board change (ie
        # device replaced after failure, but config is the same)
        #
        if not mac_address_matches and (
            not unique_id_is_mac_address or name_matches or not stored_device_name
        ):
            hass.config_entries.async_update_entry(entry, unique_id=device_mac)

        if (
            stored_device_name
            and unique_id_is_mac_address
            and not name_matches
            and not mac_address_matches
        ):
            # If we have a stored named, the unique id is a mac address
            # and nothing matches we have the wrong device and we need
            # to abort the connection. This can happen if the DHCP
            # server changes the IP address of the device and we end up
            # connecting to the wrong device.
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

        # Make sure we have the correct device name stored
        # so we can map the device to ESPHome Dashboard config
        # If we got here, we know the mac address matches or we
        # did a migration to the mac address so we can update
        # the device name.
        if not name_matches:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_DEVICE_NAME: device_info.name}
            )

        entry_data.device_info = device_info
        assert cli.api_version is not None
        entry_data.api_version = cli.api_version
        entry_data.available = True
        # Reset expected disconnect flag on successful reconnect
        # as it will be flipped to False on unexpected disconnect.
        #
        # We use this to determine if a deep sleep device should
        # be marked as unavailable or not.
        entry_data.expected_disconnect = True
        if device_info.name:
            reconnect_logic.name = device_info.name

        if device_info.bluetooth_proxy_feature_flags_compat(cli.api_version):
            entry_data.disconnect_callbacks.append(
                await async_connect_scanner(
                    hass, entry, cli, entry_data, self.domain_data.bluetooth_cache
                )
            )

        self.device_id = _async_setup_device_registry(hass, entry, entry_data)
        entry_data.async_update_device_state(hass)

        try:
            entity_infos, services = await cli.list_entities_services()
            await entry_data.async_update_static_infos(hass, entry, entity_infos)
            await _setup_services(hass, entry_data, services)
            await cli.subscribe_states(entry_data.async_update_state)
            await cli.subscribe_service_calls(self.async_on_service_call)
            await cli.subscribe_home_assistant_states(self.async_on_state_subscription)

            if device_info.voice_assistant_version:
                entry_data.disconnect_callbacks.append(
                    await cli.subscribe_voice_assistant(
                        self._handle_pipeline_start,
                        self._handle_pipeline_stop,
                    )
                )

            hass.async_create_task(entry_data.async_save_to_store())
        except APIConnectionError as err:
            _LOGGER.warning("Error getting initial data for %s: %s", self.host, err)
            # Re-connection logic will trigger after this
            await cli.disconnect()
        else:
            _async_check_firmware_version(hass, device_info, entry_data.api_version)
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
        for disconnect_cb in entry_data.disconnect_callbacks:
            disconnect_cb()
        entry_data.disconnect_callbacks = []
        entry_data.available = False
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
            entry_data.async_update_device_state(hass)

    async def on_connect_error(self, err: Exception) -> None:
        """Start reauth flow if appropriate connect error type."""
        if isinstance(
            err,
            (
                RequiresEncryptionAPIError,
                InvalidEncryptionKeyAPIError,
                InvalidAuthAPIError,
            ),
        ):
            self.entry.async_start_reauth(self.hass)

    async def async_start(self) -> None:
        """Start the esphome connection manager."""
        hass = self.hass
        entry = self.entry
        entry_data = self.entry_data

        if entry.options.get(CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS):
            async_delete_issue(hass, DOMAIN, self.services_issue)

        # Use async_listen instead of async_listen_once so that we don't deregister
        # the callback twice when shutting down Home Assistant.
        # "Unable to remove unknown listener
        # <function EventBus.async_listen_once.<locals>.onetime_listener>"
        entry_data.cleanup_callbacks.append(
            hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.on_stop)
        )

        reconnect_logic = ReconnectLogic(
            client=self.cli,
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect,
            zeroconf_instance=self.zeroconf_instance,
            name=self.host,
            on_connect_error=self.on_connect_error,
        )
        self.reconnect_logic = reconnect_logic

        infos, services = await entry_data.async_load_from_store()
        await entry_data.async_update_static_infos(hass, entry, infos)
        await _setup_services(hass, entry_data, services)

        if entry_data.device_info is not None and entry_data.device_info.name:
            reconnect_logic.name = entry_data.device_info.name
            if entry.unique_id is None:
                hass.config_entries.async_update_entry(
                    entry, unique_id=format_mac(entry_data.device_info.mac_address)
                )

        await reconnect_logic.start()
        entry_data.cleanup_callbacks.append(reconnect_logic.stop_callback)

        entry.async_on_unload(
            entry.add_update_listener(entry_data.async_update_listener)
        )


@callback
def _async_setup_device_registry(
    hass: HomeAssistant, entry: ConfigEntry, entry_data: RuntimeEntryData
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
        configuration_url = f"http://{entry.data['host']}:{device_info.webserver_port}"
    elif dashboard := async_get_dashboard(hass):
        configuration_url = f"homeassistant://hassio/ingress/{dashboard.addon_slug}"

    manufacturer = "espressif"
    if device_info.manufacturer:
        manufacturer = device_info.manufacturer
    model = device_info.model
    hw_version = None
    if device_info.project_name:
        project_name = device_info.project_name.split(".")
        manufacturer = project_name[0]
        model = project_name[1]
        hw_version = device_info.project_version

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        configuration_url=configuration_url,
        connections={(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)},
        name=entry_data.friendly_name,
        manufacturer=manufacturer,
        model=model,
        sw_version=sw_version,
        hw_version=hw_version,
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


async def _register_service(
    hass: HomeAssistant, entry_data: RuntimeEntryData, service: UserService
) -> None:
    if entry_data.device_info is None:
        raise ValueError("Device Info needs to be fetched first")
    service_name = f"{entry_data.device_info.name.replace('-', '_')}_{service.name}"
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

    async def execute_service(call: ServiceCall) -> None:
        await entry_data.client.execute_service(service, call.data)

    hass.services.async_register(
        DOMAIN, service_name, execute_service, vol.Schema(schema)
    )

    service_desc = {
        "description": (
            f"Calls the service {service.name} of the node"
            f" {entry_data.device_info.name}"
        ),
        "fields": fields,
    }

    async_set_service_schema(hass, DOMAIN, service_name, service_desc)


async def _setup_services(
    hass: HomeAssistant, entry_data: RuntimeEntryData, services: list[UserService]
) -> None:
    if entry_data.device_info is None:
        # Can happen if device has never connected or .storage cleared
        return
    old_services = entry_data.services.copy()
    to_unregister = []
    to_register = []
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

    for service in old_services.values():
        to_unregister.append(service)

    entry_data.services = {serv.key: serv for serv in services}

    for service in to_unregister:
        service_name = f"{entry_data.device_info.name}_{service.name}"
        hass.services.async_remove(DOMAIN, service_name)

    for service in to_register:
        await _register_service(hass, entry_data, service)


async def cleanup_instance(hass: HomeAssistant, entry: ConfigEntry) -> RuntimeEntryData:
    """Cleanup the esphome client if it exists."""
    domain_data = DomainData.get(hass)
    data = domain_data.pop_entry_data(entry)
    data.available = False
    for disconnect_cb in data.disconnect_callbacks:
        disconnect_cb()
    data.disconnect_callbacks = []
    for cleanup_callback in data.cleanup_callbacks:
        cleanup_callback()
    await data.async_cleanup()
    await data.client.disconnect()
    return data
