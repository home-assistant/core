"""Support for esphome devices."""
from __future__ import annotations

from collections.abc import Callable
import functools
import logging
import math
from typing import Any, Generic, NamedTuple, TypeVar, cast, overload

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    APIIntEnum,
    APIVersion,
    BadNameAPIError,
    DeviceInfo as EsphomeDeviceInfo,
    EntityCategory as EsphomeEntityCategory,
    EntityInfo,
    EntityState,
    HomeassistantServiceCall,
    InvalidEncryptionKeyAPIError,
    ReconnectLogic,
    RequiresEncryptionAPIError,
    UserService,
    UserServiceArgType,
)
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant import const
from homeassistant.components import tag, zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.template import Template

from .bluetooth import async_connect_scanner
from .domain_data import DOMAIN, DomainData

# Import config flow so that it's added to the registry
from .entry_data import RuntimeEntryData

CONF_NOISE_PSK = "noise_psk"
_LOGGER = logging.getLogger(__name__)
_R = TypeVar("_R")

STABLE_BLE_VERSION_STR = "2022.11.0"
STABLE_BLE_VERSION = AwesomeVersion(STABLE_BLE_VERSION_STR)


@callback
def _async_check_firmware_version(
    hass: HomeAssistant, device_info: EsphomeDeviceInfo
) -> None:
    """Create or delete an the ble_firmware_outdated issue."""
    # ESPHome device_info.name is the unique_id
    issue = f"ble_firmware_outdated-{device_info.name}"
    if (
        not device_info.bluetooth_proxy_version
        # If the device has a project name its up to that project
        # to tell them about the firmware version update so we don't notify here
        or device_info.project_name
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
        learn_more_url=f"https://esphome.io/changelog/{STABLE_BLE_VERSION_STR}.html",
        translation_key="ble_firmware_outdated",
        translation_placeholders={"name": device_info.name},
    )


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up the esphome component."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]
    noise_psk = entry.data.get(CONF_NOISE_PSK)
    device_id: str | None = None

    zeroconf_instance = await zeroconf.async_get_instance(hass)

    cli = APIClient(
        host,
        port,
        password,
        client_info=f"Home Assistant {const.__version__}",
        zeroconf_instance=zeroconf_instance,
        noise_psk=noise_psk,
    )

    domain_data = DomainData.get(hass)
    entry_data = RuntimeEntryData(
        client=cli,
        entry_id=entry.entry_id,
        store=domain_data.get_or_create_store(hass, entry),
    )
    domain_data.set_entry_data(entry, entry_data)

    async def on_stop(event: Event) -> None:
        """Cleanup the socket client on HA stop."""
        await _cleanup_instance(hass, entry)

    # Use async_listen instead of async_listen_once so that we don't deregister
    # the callback twice when shutting down Home Assistant.
    # "Unable to remove unknown listener <function EventBus.async_listen_once.<locals>.onetime_listener>"
    entry_data.cleanup_callbacks.append(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, on_stop)
    )

    @callback
    def async_on_service_call(service: HomeassistantServiceCall) -> None:
        """Call service when user automation in ESPHome config is triggered."""
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
            # ESPHome uses servicecall packet for both events and service calls
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
        else:
            hass.async_create_task(
                hass.services.async_call(
                    domain, service_name, service_data, blocking=True
                )
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

    async def on_connect() -> None:
        """Subscribe to states and list entities on successful API login."""
        nonlocal device_id
        try:
            device_info = await cli.device_info()
            entry_data.device_info = device_info
            assert cli.api_version is not None
            entry_data.api_version = cli.api_version
            entry_data.available = True
            if entry_data.device_info.name:
                cli.expected_name = entry_data.device_info.name
                reconnect_logic.name = entry_data.device_info.name
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
            if entry_data.device_info.bluetooth_proxy_version:
                entry_data.disconnect_callbacks.append(
                    await async_connect_scanner(hass, entry, cli, entry_data)
                )

            hass.async_create_task(entry_data.async_save_to_store())
        except APIConnectionError as err:
            _LOGGER.warning("Error getting initial data for %s: %s", host, err)
            # Re-connection logic will trigger after this
            await cli.disconnect()
        else:
            _async_check_firmware_version(hass, device_info)

    async def on_disconnect() -> None:
        """Run disconnect callbacks on API disconnect."""
        name = entry_data.device_info.name if entry_data.device_info else host
        _LOGGER.debug("%s: %s disconnected, running disconnected callbacks", name, host)
        for disconnect_cb in entry_data.disconnect_callbacks:
            disconnect_cb()
        entry_data.disconnect_callbacks = []
        entry_data.available = False
        entry_data.async_update_device_state(hass)

    async def on_connect_error(err: Exception) -> None:
        """Start reauth flow if appropriate connect error type."""
        if isinstance(err, (RequiresEncryptionAPIError, InvalidEncryptionKeyAPIError)):
            entry.async_start_reauth(hass)
        if isinstance(err, BadNameAPIError):
            _LOGGER.warning(
                "Name of device %s changed to %s, potentially due to IP reassignment",
                cli.expected_name,
                err.received_name,
            )

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
        cli.expected_name = entry_data.device_info.name
        reconnect_logic.name = entry_data.device_info.name
        if entry.unique_id is None:
            hass.config_entries.async_update_entry(
                entry, unique_id=entry_data.device_info.name
            )

    await reconnect_logic.start()
    entry_data.cleanup_callbacks.append(reconnect_logic.stop_callback)

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
        name=device_info.name,
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
        "description": f"Calls the service {service.name} of the node {entry_data.device_info.name}",
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


_InfoT = TypeVar("_InfoT", bound=EntityInfo)
_EntityT = TypeVar("_EntityT", bound="EsphomeEntity[Any,Any]")
_StateT = TypeVar("_StateT", bound=EntityState)


async def platform_async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    *,
    component_key: str,
    info_type: type[_InfoT],
    entity_type: type[_EntityT],
    state_type: type[_StateT],
) -> None:
    """Set up an esphome platform.

    This method is in charge of receiving, distributing and storing
    info and state updates.
    """
    entry_data: RuntimeEntryData = DomainData.get(hass).get_entry_data(entry)
    entry_data.info[component_key] = {}
    entry_data.old_info[component_key] = {}
    entry_data.state.setdefault(state_type, {})

    @callback
    def async_list_entities(infos: list[EntityInfo]) -> None:
        """Update entities of this platform when entities are listed."""
        old_infos = entry_data.info[component_key]
        new_infos: dict[int, EntityInfo] = {}
        add_entities: list[_EntityT] = []
        for info in infos:
            if not isinstance(info, info_type):
                # Filter out infos that don't belong to this platform.
                continue

            if info.key in old_infos:
                # Update existing entity
                old_infos.pop(info.key)
            else:
                # Create new entity
                entity = entity_type(entry_data, component_key, info.key, state_type)
                add_entities.append(entity)
            new_infos[info.key] = info

        # Remove old entities
        for info in old_infos.values():
            entry_data.async_remove_entity(hass, component_key, info.key)

        # First copy the now-old info into the backup object
        entry_data.old_info[component_key] = entry_data.info[component_key]
        # Then update the actual info
        entry_data.info[component_key] = new_infos

        # Add entities to Home Assistant
        async_add_entities(add_entities)

    signal = f"esphome_{entry.entry_id}_on_list"
    entry_data.cleanup_callbacks.append(
        async_dispatcher_connect(hass, signal, async_list_entities)
    )


def esphome_state_property(
    func: Callable[[_EntityT], _R]
) -> Callable[[_EntityT], _R | None]:
    """Wrap a state property of an esphome entity.

    This checks if the state object in the entity is set, and
    prevents writing NAN values to the Home Assistant state machine.
    """

    @functools.wraps(func)
    def _wrapper(self: _EntityT) -> _R | None:
        # pylint: disable-next=protected-access
        if not self._has_state:
            return None
        val = func(self)
        if isinstance(val, float) and math.isnan(val):
            # Home Assistant doesn't use NAN values in state machine
            # (not JSON serializable)
            return None
        return val

    return _wrapper


_EnumT = TypeVar("_EnumT", bound=APIIntEnum)
_ValT = TypeVar("_ValT")


class EsphomeEnumMapper(Generic[_EnumT, _ValT]):
    """Helper class to convert between hass and esphome enum values."""

    def __init__(self, mapping: dict[_EnumT, _ValT]) -> None:
        """Construct a EsphomeEnumMapper."""
        # Add none mapping
        augmented_mapping: dict[_EnumT | None, _ValT | None] = mapping  # type: ignore[assignment]
        augmented_mapping[None] = None

        self._mapping = augmented_mapping
        self._inverse: dict[_ValT, _EnumT] = {v: k for k, v in mapping.items()}

    @overload
    def from_esphome(self, value: _EnumT) -> _ValT:
        ...

    @overload
    def from_esphome(self, value: _EnumT | None) -> _ValT | None:
        ...

    def from_esphome(self, value: _EnumT | None) -> _ValT | None:
        """Convert from an esphome int representation to a hass string."""
        return self._mapping[value]

    def from_hass(self, value: _ValT) -> _EnumT:
        """Convert from a hass string to a esphome int representation."""
        return self._inverse[value]


ICON_SCHEMA = vol.Schema(cv.icon)


ENTITY_CATEGORIES: EsphomeEnumMapper[
    EsphomeEntityCategory, EntityCategory | None
] = EsphomeEnumMapper(
    {
        EsphomeEntityCategory.NONE: None,
        EsphomeEntityCategory.CONFIG: EntityCategory.CONFIG,
        EsphomeEntityCategory.DIAGNOSTIC: EntityCategory.DIAGNOSTIC,
    }
)


class EsphomeEntity(Entity, Generic[_InfoT, _StateT]):
    """Define a base esphome entity."""

    _attr_should_poll = False

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        component_key: str,
        key: int,
        state_type: type[_StateT],
    ) -> None:
        """Initialize."""
        self._entry_data = entry_data
        self._component_key = component_key
        self._key = key
        self._state_type = state_type

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                (
                    f"esphome_{self._entry_id}_remove_"
                    f"{self._component_key}_{self._key}"
                ),
                functools.partial(self.async_remove, force_remove=True),
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"esphome_{self._entry_id}_on_device_update",
                self._on_device_update,
            )
        )

        self.async_on_remove(
            self._entry_data.async_subscribe_state_update(
                self._state_type, self._key, self._on_state_update
            )
        )

    @callback
    def _on_state_update(self) -> None:
        # Behavior can be changed in child classes
        self.async_write_ha_state()

    @callback
    def _on_device_update(self) -> None:
        """Update the entity state when device info has changed."""
        if self._entry_data.available:
            # Don't update the HA state yet when the device comes online.
            # Only update the HA state when the full state arrives
            # through the next entity state packet.
            return
        self._on_state_update()

    @property
    def _entry_id(self) -> str:
        return self._entry_data.entry_id

    @property
    def _api_version(self) -> APIVersion:
        return self._entry_data.api_version

    @property
    def _static_info(self) -> _InfoT:
        # Check if value is in info database. Use a single lookup.
        info = self._entry_data.info[self._component_key].get(self._key)
        if info is not None:
            return cast(_InfoT, info)
        # This entity is in the removal project and has been removed from .info
        # already, look in old_info
        return cast(_InfoT, self._entry_data.old_info[self._component_key][self._key])

    @property
    def _device_info(self) -> EsphomeDeviceInfo:
        assert self._entry_data.device_info is not None
        return self._entry_data.device_info

    @property
    def _client(self) -> APIClient:
        return self._entry_data.client

    @property
    def _state(self) -> _StateT:
        return cast(_StateT, self._entry_data.state[self._state_type][self._key])

    @property
    def _has_state(self) -> bool:
        return self._key in self._entry_data.state[self._state_type]

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        device = self._device_info

        if device.has_deep_sleep:
            # During deep sleep the ESP will not be connectable (by design)
            # For these cases, show it as available
            return True

        return self._entry_data.available

    @property
    def unique_id(self) -> str | None:
        """Return a unique id identifying the entity."""
        if not self._static_info.unique_id:
            return None
        return self._static_info.unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._device_info.mac_address)}
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._static_info.name

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if not self._static_info.icon:
            return None

        return cast(str, ICON_SCHEMA(self._static_info.icon))

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return not self._static_info.disabled_by_default

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the category of the entity, if any."""
        if not self._static_info.entity_category:
            return None
        return ENTITY_CATEGORIES.from_esphome(self._static_info.entity_category)
