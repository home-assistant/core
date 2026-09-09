"""Support for RFXtrx devices."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

import binascii
from collections.abc import Callable, Mapping
import logging
from types import MappingProxyType
from typing import Any, NamedTuple, cast

import RFXtrx as rfxtrxmod

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import EventDeviceRegistryUpdatedData
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_EVENT_CODE,
    CONF_PROTOCOLS,
    DATA_RFXOBJECT,
    DEVICE_PACKET_TYPE_LIGHTING4,
    DOMAIN,
    EVENT_RFXTRX_EVENT,
    SIGNAL_EVENT,
    SUBENTRY_TYPE_DEVICE,
)
from .services import async_setup_services

DEFAULT_OFF_DELAY = 2.0

CONNECT_TIMEOUT = 60.0

RELOAD_DEBOUNCE_COOLDOWN = 0

_LOGGER = logging.getLogger(__name__)


class DeviceTuple(NamedTuple):
    """Representation of a device in rfxtrx."""

    packettype: str
    subtype: str
    id_string: str

    @property
    def unique_id(self) -> str:
        """Unique identifier of this device tuple."""
        return f"{self.packettype}_{self.subtype}_{self.id_string}"


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up RFXtrx services."""
    hass.data.setdefault(DOMAIN, {})
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the RFXtrx component."""
    hass.data.setdefault(DOMAIN, {})

    await async_setup_internal(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload RFXtrx component."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    rfx_object = hass.data[DOMAIN][DATA_RFXOBJECT]
    await hass.async_add_executor_job(rfx_object.close_connection)

    hass.data[DOMAIN].pop(DATA_RFXOBJECT)

    return True


def _create_rfx(
    config: Mapping[str, Any], event_callback: Callable[[rfxtrxmod.RFXtrxEvent], None]
) -> rfxtrxmod.Connect:
    """Construct a rfx object based on config."""

    modes = config.get(CONF_PROTOCOLS)

    if modes:
        _LOGGER.debug("Using modes: %s", ",".join(modes))
    else:
        _LOGGER.debug("No modes defined, using device configuration")

    if config[CONF_PORT] is not None:
        # If port is set then we create a TCP connection
        transport = rfxtrxmod.PyNetworkTransport((config[CONF_HOST], config[CONF_PORT]))
    else:
        transport = rfxtrxmod.PySerialTransport(config[CONF_DEVICE])

    rfx = rfxtrxmod.Connect(
        transport,
        event_callback,
        modes=modes,
    )

    try:
        rfx.connect(CONNECT_TIMEOUT)
    except TimeoutError as exc:
        raise ConfigEntryNotReady("Timeout on connect") from exc
    except rfxtrxmod.RFXtrxTransportError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    return rfx


def _get_device_lookup(entry: ConfigEntry) -> dict[DeviceTuple, ConfigSubentry]:
    """Get a lookup structure for devices."""
    lookup: dict[DeviceTuple, ConfigSubentry] = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
            continue
        if (event := get_rfx_object(subentry.data[CONF_EVENT_CODE])) is None:
            continue
        device_id = get_device_tuple_from_device(
            event.device, data_bits=subentry.data.get(CONF_DATA_BITS)
        )
        lookup[device_id] = subentry
    return lookup


async def async_setup_internal(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the RFXtrx component."""
    config = entry.data

    # Setup some per device config
    devices = _get_device_lookup(entry)
    pt2262_devices: set[str] = set()

    device_registry = dr.async_get(hass)

    # Automatic discovery persists new devices as subentries directly, avoid
    # reloads for these.
    pending_internal_updates = 0

    async def _async_do_reload() -> None:
        await hass.config_entries.async_reload(entry.entry_id)

    # Debounced so a flow that updates multiple subentries results in a single
    # reload reflecting all of them.
    reload_debouncer = Debouncer(
        hass,
        _LOGGER,
        cooldown=RELOAD_DEBOUNCE_COOLDOWN,
        immediate=False,
        function=_async_do_reload,
    )
    entry.async_on_unload(reload_debouncer.async_shutdown)

    async def _async_reload_on_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Reload the entry when it is updated through a config/subentry flow."""
        nonlocal pending_internal_updates
        if pending_internal_updates > 0:
            pending_internal_updates -= 1
            return
        await reload_debouncer.async_call()

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))

    # Declare the Handle event
    @callback
    def async_handle_receive(event: rfxtrxmod.RFXtrxEvent) -> None:
        """Handle received messages from RFXtrx gateway."""

        if isinstance(event, rfxtrxmod.ConnectionLost):
            _LOGGER.warning("Connection was lost, triggering reload")
            hass.async_create_task(
                hass.config_entries.async_reload(entry.entry_id),
                f"config entry reload {entry.title} {entry.domain} {entry.entry_id}",
            )
            return

        if not event.device or not event.device.id_string:
            return

        event_data = {
            "packet_type": event.device.packettype,
            "sub_type": event.device.subtype,
            "type_string": event.device.type_string,
            "id_string": event.device.id_string,
            "data": binascii.hexlify(event.data).decode("ASCII"),
            "values": getattr(event, "values", None),
        }

        _LOGGER.debug("Receive RFXCOM event: %s", event_data)

        data_bits = get_device_data_bits(event.device, devices)
        device_id = get_device_tuple_from_device(event.device, data_bits=data_bits)

        if device_id not in devices:
            if config[CONF_AUTOMATIC_ADD]:
                _add_device(event, device_id)
            else:
                return

        if event.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            find_possible_pt2262_device(pt2262_devices, event.device.id_string)
            pt2262_devices.add(event.device.id_string)

        subentry = devices[device_id]
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, subentry.subentry_id),
            entry.entry_id,
        )
        if device_entry:
            event_data[ATTR_DEVICE_ID] = device_entry.id

        # Callback to HA registered components.
        async_dispatcher_send(hass, SIGNAL_EVENT, event, device_id)

        # Signal event to any other listeners
        hass.bus.async_fire(EVENT_RFXTRX_EVENT, event_data)

    @callback
    def _add_device(event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple) -> None:
        """Add a device to config entry."""
        nonlocal pending_internal_updates
        event_code = binascii.hexlify(event.data).decode("ASCII")

        _LOGGER.debug(
            "Added device (Device ID: %s Class: %s Sub: %s, Event: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
            event_code,
        )

        subentry = ConfigSubentry(
            data=MappingProxyType({CONF_EVENT_CODE: event_code}),
            subentry_type=SUBENTRY_TYPE_DEVICE,
            title=f"{event.device.type_string} {device_id.id_string}",
            unique_id=device_id.unique_id,
        )
        pending_internal_updates += 1
        hass.config_entries.async_add_subentry(entry, subentry)
        devices[device_id] = subentry

    @callback
    def _remove_device(subentry_id: str) -> None:
        nonlocal pending_internal_updates
        device_id = next(
            (d for d, s in devices.items() if s.subentry_id == subentry_id), None
        )
        if device_id is not None:
            devices.pop(device_id)
        pending_internal_updates += 1
        hass.config_entries.async_remove_subentry(entry, subentry_id)

    @callback
    def _updated_device(event: Event[EventDeviceRegistryUpdatedData]) -> None:
        if event.data["action"] != "remove":
            return
        device = event.data["device"]
        if device["config_entry_id"] != entry.entry_id:
            return
        subentry_id = get_subentry_id_from_identifiers(device["identifiers"])
        if subentry_id and subentry_id in entry.subentries:
            _remove_device(subentry_id)

    # Initialize library
    rfx_object = await hass.async_add_executor_job(
        _create_rfx, config, lambda event: hass.add_job(async_handle_receive, event)
    )

    # Uses legacy hass.data[DOMAIN] pattern
    # pylint: disable-next=home-assistant-use-runtime-data
    hass.data[DOMAIN][DATA_RFXOBJECT] = rfx_object

    entry.async_on_unload(
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _updated_device)
    )

    def _shutdown_rfxtrx(event: Event) -> None:
        """Close connection with RFXtrx."""
        rfx_object.close_connection()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_rfxtrx)
    )


async def async_setup_platform_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    supported: Callable[[rfxtrxmod.RFXtrxEvent], bool],
    constructor: Callable[
        [
            rfxtrxmod.RFXtrxEvent,
            rfxtrxmod.RFXtrxEvent | None,
            ConfigSubentry,
        ],
        list[Entity],
    ],
) -> None:
    """Set up config entry."""
    device_ids: set[DeviceTuple] = set()

    # Add entities from config
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
            continue
        if (event := get_rfx_object(subentry.data[CONF_EVENT_CODE])) is None:
            _LOGGER.error("Invalid device: %s", subentry.data[CONF_EVENT_CODE])
            continue
        if not supported(event):
            continue

        device_id = get_device_tuple_from_device(
            event.device, data_bits=subentry.data.get(CONF_DATA_BITS)
        )
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        entities = constructor(event, None, subentry)
        async_add_entities(entities, config_subentry_id=subentry.subentry_id)

    # If automatic add is on, hookup listener
    if config_entry.data[CONF_AUTOMATIC_ADD]:

        @callback
        def _update(event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple) -> None:
            """Handle light updates from the RFXtrx gateway."""
            if not supported(event):
                return

            if device_id in device_ids:
                return
            device_ids.add(device_id)
            subentry = next(
                (
                    s
                    for s in config_entry.subentries.values()
                    if s.unique_id == device_id.unique_id
                ),
                None,
            )
            # The subentry is always created before this signal is dispatched.
            assert subentry
            async_add_entities(
                constructor(event, event, subentry),
                config_subentry_id=subentry.subentry_id,
            )

        config_entry.async_on_unload(
            async_dispatcher_connect(hass, SIGNAL_EVENT, _update)
        )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    version = entry.version

    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if version == 1:
        # Convert from old tuple based device identifiers to standard string

        device_registry = dr.async_get(hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            identifiers = set()
            for identifier in device_entry.identifiers:
                if identifier[0] == DOMAIN and len(cast(tuple, identifier)) == 4:
                    legacy_identifier = cast(tuple[str, str, str, str], identifier)
                    identifier = (
                        DOMAIN,
                        DeviceTuple(
                            packettype=legacy_identifier[1],
                            subtype=legacy_identifier[2],
                            id_string=legacy_identifier[3],
                        ).unique_id,
                    )
                identifiers.add(identifier)
            device_registry.async_update_device(
                device_entry.id, new_identifiers=identifiers
            )
        version = 2
        hass.config_entries.async_update_entry(entry, version=version)

    if version == 2:
        # Convert per-device config stored on the config entry into subentries

        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        # Pre-seeded from existing subentries so a migration retried after a
        # partially completed run (or two legacy event codes that compute the
        # same device, e.g. duplicate PT2262/cover codes) does not try to add
        # a second subentry with the same unique_id and abort.
        subentry_by_unique_id: dict[str, str] = {
            subentry.unique_id: subentry.subentry_id
            for subentry in entry.subentries.values()
            if subentry.unique_id is not None
        }

        for event_code, entity_info in entry.data[CONF_DEVICES].items():
            if (event := get_rfx_object(event_code)) is None:
                continue
            device_id = get_device_tuple_from_device(
                event.device, data_bits=entity_info.get(CONF_DATA_BITS)
            )
            if device_id.unique_id in subentry_by_unique_id:
                continue
            subentry_data = {
                key: value
                for key, value in entity_info.items()
                if key != CONF_DEVICE_ID
            }
            subentry_data[CONF_EVENT_CODE] = event_code
            subentry = ConfigSubentry(
                data=MappingProxyType(subentry_data),
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title=f"{event.device.type_string} {device_id.id_string}",
                unique_id=device_id.unique_id,
            )
            hass.config_entries.async_add_subentry(entry, subentry)
            subentry_by_unique_id[device_id.unique_id] = subentry.subentry_id

        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            for identifier in device_entry.identifiers:
                if identifier[0] != DOMAIN:
                    continue
                unique_id = identifier[1]
                if unique_id not in subentry_by_unique_id:
                    continue

                subentry_id = subentry_by_unique_id[unique_id]
                new_identifiers = {
                    other for other in device_entry.identifiers if other[0] != DOMAIN
                } | {(DOMAIN, subentry_id)}

                # Entities must be moved to the new subentry before the device
                # is, since moving the device fires an update event that makes
                # the entity registry purge any of its entities still pointing
                # at the device's *previous* subentry.
                for entity_entry in er.async_entries_for_device(
                    entity_registry, device_entry.id, include_disabled_entities=True
                ):
                    if entity_entry.config_entry_id != entry.entry_id:
                        continue
                    if entity_entry.config_subentry_id == subentry_id:
                        continue
                    suffix = entity_entry.unique_id.removeprefix(unique_id)
                    new_unique_id = f"{subentry_id}{suffix}"
                    if (
                        entity_entry.domain == Platform.EVENT
                        and entity_entry.translation_key
                    ):
                        # Event entities lacked unique id suffixes.
                        new_unique_id = (
                            f"{new_unique_id}_{entity_entry.translation_key}"
                        )
                    entity_registry.async_update_entity(
                        entity_entry.entity_id,
                        config_entry_id=entry.entry_id,
                        config_subentry_id=subentry_id,
                        new_unique_id=new_unique_id,
                    )

                device_registry.async_update_device(
                    device_entry.id,
                    new_config_entry_id=entry.entry_id,
                    new_config_subentry_id=subentry_id,
                    new_identifiers=new_identifiers,
                )
                break

        new_data = {
            key: value for key, value in entry.data.items() if key != CONF_DEVICES
        }
        version = 3
        hass.config_entries.async_update_entry(entry, data=new_data, version=version)

    _LOGGER.debug(
        "Migration to version %s.%s successful", entry.version, entry.minor_version
    )
    return True


def get_rfx_object(packetid: str) -> rfxtrxmod.RFXtrxEvent | None:
    """Return the RFXObject with the packetid."""
    try:
        binarypacket = bytearray.fromhex(packetid)
    except ValueError:
        return None
    return rfxtrxmod.RFXtrxTransport.parse(binarypacket)


def get_pt2262_deviceid(device_id: str, nb_data_bits: int | None) -> bytes | None:
    """Extract and return the address bits from a Lighting4/PT2262 packet."""
    if nb_data_bits is None:
        return None

    try:
        data = bytearray.fromhex(device_id)
    except ValueError:
        return None
    mask = 0xFF & ~((1 << nb_data_bits) - 1)

    data[len(data) - 1] &= mask

    return binascii.hexlify(data)


def get_pt2262_cmd(device_id: str, data_bits: int) -> str | None:
    """Extract and return the data bits from a Lighting4/PT2262 packet."""
    try:
        data = bytearray.fromhex(device_id)
    except ValueError:
        return None

    mask = 0xFF & ((1 << data_bits) - 1)

    return hex(data[-1] & mask)


def get_device_data_bits(
    device: rfxtrxmod.RFXtrxDevice, devices: dict[DeviceTuple, ConfigSubentry]
) -> int | None:
    """Deduce data bits for device based on a cache of device bits."""
    data_bits = None
    if device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
        for device_id, subentry in devices.items():
            bits = subentry.data.get(CONF_DATA_BITS)
            if get_device_tuple_from_device(device, bits) == device_id:
                data_bits = bits
                break
    return data_bits


def find_possible_pt2262_device(device_ids: set[str], device_id: str) -> str | None:
    """Look for the device which id matches the given device_id parameter."""
    for dev_id in device_ids:
        if len(dev_id) == len(device_id):
            size = None
            for i, (char1, char2) in enumerate(zip(dev_id, device_id, strict=False)):
                if char1 != char2:
                    break
                size = i
            if size is not None:
                size = len(dev_id) - size - 1
                _LOGGER.debug(
                    (
                        "Found possible device %s for %s "
                        "with the following configuration:\n"
                        "data_bits=%d\n"
                        "command_on=0x%s\n"
                        "command_off=0x%s\n"
                    ),
                    device_id,
                    dev_id,
                    size * 4,
                    dev_id[-size:],
                    device_id[-size:],
                )
                return dev_id
    return None


def get_device_tuple_from_device(
    device: rfxtrxmod.RFXtrxDevice, data_bits: int | None = None
) -> DeviceTuple:
    """Calculate a device id for device."""
    id_string: str = device.id_string
    if (
        data_bits
        and device.packettype == DEVICE_PACKET_TYPE_LIGHTING4
        and (masked_id := get_pt2262_deviceid(id_string, data_bits))
    ):
        id_string = masked_id.decode("ASCII")

    return DeviceTuple(f"{device.packettype:x}", f"{device.subtype:x}", id_string)


def get_subentry_id_from_identifiers(
    identifiers: set[tuple[str, str]],
) -> str | None:
    """Get the config subentry id from a set of device registry identifiers."""
    return next(
        (
            identifier[1]
            for identifier in identifiers
            # Legacy 4-tuple identifiers also start with DOMAIN, so only
            # 2-tuples can be trusted to hold a subentry id.
            if identifier[0] == DOMAIN and len(cast(tuple, identifier)) == 2
        ),
        None,
    )


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Remove config entry from a device.

    The actual cleanup is done in the device registry event
    """
    return True
