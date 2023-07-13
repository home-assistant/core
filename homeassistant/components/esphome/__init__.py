"""Support for esphome devices."""
from __future__ import annotations

import logging
from typing import Any, NamedTuple, TypeVar

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
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    __version__ as ha_version,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .bluetooth import async_connect_scanner
from .const import (
    CONF_ALLOW_SERVICE_CALLS,
    DEFAULT_ALLOW_SERVICE_CALLS,
    DOMAIN,
)
from .dashboard import async_get_dashboard, async_setup as async_setup_dashboard
from .domain_data import DomainData

# Import config flow so that it's added to the registry
from .entry_data import RuntimeEntryData
from .voice_assistant import VoiceAssistantUDPServer

CONF_DEVICE_NAME = "device_name"
CONF_NOISE_PSK = "noise_psk"
_LOGGER = logging.getLogger(__name__)
_R = TypeVar("_R")

STABLE_BLE_VERSION_STR = "2023.6.0"
STABLE_BLE_VERSION = AwesomeVersion(STABLE_BLE_VERSION_STR)
PROJECT_URLS = {
    "esphome.bluetooth-proxy": "https://esphome.github.io/bluetooth-proxies/",
}
DEFAULT_URL = f"https://esphome.io/changelog/{STABLE_BLE_VERSION_STR}.html"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the esphome component."""
    await async_setup_dashboard(hass)
    return True


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up the esphome component."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]
    noise_psk = entry.data.get(CONF_NOISE_PSK)
    device_id: str = None  # type: ignore[assignment]

    zeroconf_instance = await zeroconf.async_get_instance(hass)

    cli = APIClient(
        host,
        port,
        password,
        client_info=f"Home Assistant {ha_version}",
        zeroconf_instance=zeroconf_instance,
        noise_psk=noise_psk,
    )

    services_issue = f"service_calls_not_enabled-{entry.unique_id}"
    if entry.options.get(CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS):
        async_delete_issue(hass, DOMAIN, services_issue)

    domain_data = DomainData.get(hass)
    entry_data = RuntimeEntryData(
        client=cli,
        entry_id=entry.entry_id,
        store=domain_data.get_or_create_store(hass, entry),
        original_options=dict(entry.options),
    )
    domain_data.set_entry_data(entry, entry_data)

    async def on_stop(event: Event) -> None:
        """Cleanup the socket client on HA stop."""
        await _cleanup_instance(hass, entry)

    # Use async_listen instead of async_listen_once so that we don't deregister
    # the callback twice when shutting down Home Assistant.
    # "Unable to remove unknown listener
    # <function EventBus.async_listen_once.<locals>.onetime_listener>"
    entry_data.cleanup_callbacks.append(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, on_stop)
    )

    @callback
    def async_on_service_call(service: HomeassistantServiceCall) -> None:
        """Call service when user automation in ESPHome config is triggered."""
        device_info = entry_data.device_info
        assert device_info is not None
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
                _LOGGER.error("Error rendering data template for %s: %s", host, ex)
                return

        if service.is_event:
            # ESPHome uses service call packet for both events and service calls
            # Ensure the user can only send events of form 'esphome.xyz'
            if domain != "esphome":
                _LOGGER.error(
                    "Can only generate events under esphome domain! (%s)", host
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
        elif entry.options.get(CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS):
            hass.async_create_task(
                hass.services.async_call(
                    domain, service_name, service_data, blocking=True
                )
            )
        else:
            async_create_issue(
                hass,
                DOMAIN,
                services_issue,
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
        entity_id: str, attribute: str | None, state: State | None
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

        await cli.send_home_assistant_state(entity_id, attribute, str(send_state))

    @callback
    def async_on_state_subscription(
        entity_id: str, attribute: str | None = None
    ) -> None:
        """Subscribe and forward states for requested entities."""

        async def send_home_assistant_state_event(event: Event) -> None:
            """Forward Home Assistant states updates to ESPHome."""

            # Only communicate changes to the state or attribute tracked
            if event.data.get("new_state") is None or (
                event.data.get("old_state") is not None
                and "new_state" in event.data
                and (
                    (
                        not attribute
                        and event.data["old_state"].state
                        == event.data["new_state"].state
                    )
                    or (
                        attribute
                        and attribute in event.data["old_state"].attributes
                        and attribute in event.data["new_state"].attributes
                        and event.data["old_state"].attributes[attribute]
                        == event.data["new_state"].attributes[attribute]
                    )
                )
            ):
                return

            await _send_home_assistant_state(
                event.data["entity_id"], attribute, event.data.get("new_state")
            )

        unsub = async_track_state_change_event(
            hass, [entity_id], send_home_assistant_state_event
        )
        entry_data.disconnect_callbacks.append(unsub)

        # Send initial state
        hass.async_create_task(
            _send_home_assistant_state(entity_id, attribute, hass.states.get(entity_id))
        )

    voice_assistant_udp_server: VoiceAssistantUDPServer | None = None

    def _handle_pipeline_event(
        event_type: VoiceAssistantEventType, data: dict[str, str] | None
    ) -> None:
        cli.send_voice_assistant_event(event_type, data)

    def _handle_pipeline_finished() -> None:
        nonlocal voice_assistant_udp_server

        entry_data.async_set_assist_pipeline_state(False)

        if voice_assistant_udp_server is not None:
            voice_assistant_udp_server.close()
            voice_assistant_udp_server = None

    async def _handle_pipeline_start(conversation_id: str, use_vad: bool) -> int | None:
        """Start a voice assistant pipeline."""
        nonlocal voice_assistant_udp_server

        if voice_assistant_udp_server is not None:
            return None

        voice_assistant_udp_server = VoiceAssistantUDPServer(
            hass, entry_data, _handle_pipeline_event, _handle_pipeline_finished
        )
        port = await voice_assistant_udp_server.start_server()

        hass.async_create_background_task(
            voice_assistant_udp_server.run_pipeline(
                device_id=device_id,
                conversation_id=conversation_id or None,
                use_vad=use_vad,
            ),
            "esphome.voice_assistant_udp_server.run_pipeline",
        )
        entry_data.async_set_assist_pipeline_state(True)

        return port

    async def _handle_pipeline_stop() -> None:
        """Stop a voice assistant pipeline."""
        nonlocal voice_assistant_udp_server

        if voice_assistant_udp_server is not None:
            voice_assistant_udp_server.stop()

    async def on_connect() -> None:
        """Subscribe to states and list entities on successful API login."""
        nonlocal device_id
        try:
            device_info = await cli.device_info()

            # Migrate config entry to new unique ID if necessary
            # This was changed in 2023.1
            if entry.unique_id != format_mac(device_info.mac_address):
                hass.config_entries.async_update_entry(
                    entry, unique_id=format_mac(device_info.mac_address)
                )

            # Make sure we have the correct device name stored
            # so we can map the device to ESPHome Dashboard config
            if entry.data.get(CONF_DEVICE_NAME) != device_info.name:
                hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_DEVICE_NAME: device_info.name}
                )

            entry_data.device_info = device_info
            assert cli.api_version is not None
            entry_data.api_version = cli.api_version
            entry_data.available = True
            entry_data.expected_disconnect = True
            if entry_data.device_info.name:
                reconnect_logic.name = entry_data.device_info.name

            if device_info.bluetooth_proxy_feature_flags_compat(cli.api_version):
                entry_data.disconnect_callbacks.append(
                    await async_connect_scanner(hass, entry, cli, entry_data)
                )

            device_id = _async_setup_device_registry(
                hass, entry, entry_data.device_info
            )
            entry_data.async_update_device_state(hass)

            entity_infos, services = await cli.list_entities_services()
            await entry_data.async_update_static_infos(hass, entry, entity_infos)
            await _setup_services(hass, entry_data, services)
            await cli.subscribe_states(entry_data.async_update_state)
            await cli.subscribe_service_calls(async_on_service_call)
            await cli.subscribe_home_assistant_states(async_on_state_subscription)

            if device_info.voice_assistant_version:
                entry_data.disconnect_callbacks.append(
                    await cli.subscribe_voice_assistant(
                        _handle_pipeline_start,
                        _handle_pipeline_stop,
                    )
                )

            hass.async_create_task(entry_data.async_save_to_store())
        except APIConnectionError as err:
            _LOGGER.warning("Error getting initial data for %s: %s", host, err)
            # Re-connection logic will trigger after this
            await cli.disconnect()
        else:
            _async_check_firmware_version(hass, device_info, entry_data.api_version)
            _async_check_using_api_password(hass, device_info, bool(password))

    async def on_disconnect(expected_disconnect: bool) -> None:
        """Run disconnect callbacks on API disconnect."""
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

    async def on_connect_error(err: Exception) -> None:
        """Start reauth flow if appropriate connect error type."""
        if isinstance(
            err,
            (
                RequiresEncryptionAPIError,
                InvalidEncryptionKeyAPIError,
                InvalidAuthAPIError,
            ),
        ):
            entry.async_start_reauth(hass)

    reconnect_logic = ReconnectLogic(
        client=cli,
        on_connect=on_connect,
        on_disconnect=on_disconnect,
        zeroconf_instance=zeroconf_instance,
        name=host,
        on_connect_error=on_connect_error,
    )

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

    entry.async_on_unload(entry.add_update_listener(entry_data.async_update_listener))

    return True


@callback
def _async_setup_device_registry(
    hass: HomeAssistant, entry: ConfigEntry, device_info: EsphomeDeviceInfo
) -> str:
    """Set up device registry feature for a particular config entry."""
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
        name=device_info.friendly_name or device_info.name,
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


async def _cleanup_instance(
    hass: HomeAssistant, entry: ConfigEntry
) -> RuntimeEntryData:
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an esphome config entry."""
    entry_data = await _cleanup_instance(hass, entry)
    return await hass.config_entries.async_unload_platforms(
        entry, entry_data.loaded_platforms
    )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove an esphome config entry."""
    await DomainData.get(hass).get_or_create_store(hass, entry).async_remove()
