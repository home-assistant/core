"""Support for RFXtrx devices."""
from __future__ import annotations

import asyncio
import binascii
from collections.abc import Callable, Mapping
import copy
import logging
from typing import Any, NamedTuple, cast

import RFXtrx as rfxtrxmod
import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
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
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_EVENT,
    COMMAND_GROUP_LIST,
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_PROTOCOLS,
    DATA_RFXOBJECT,
    DEVICE_PACKET_TYPE_LIGHTING4,
    DOMAIN,
    EVENT_RFXTRX_EVENT,
    SERVICE_SEND,
)

DEFAULT_OFF_DELAY = 2.0

SIGNAL_EVENT = f"{DOMAIN}_event"

_LOGGER = logging.getLogger(__name__)


class DeviceTuple(NamedTuple):
    """Representation of a device in rfxtrx."""

    packettype: str
    subtype: str
    id_string: str


def _bytearray_string(data: Any) -> bytearray:
    val = cv.string(data)
    try:
        return bytearray.fromhex(val)
    except ValueError as err:
        raise vol.Invalid(
            "Data must be a hex string with multiple of two characters"
        ) from err


SERVICE_SEND_SCHEMA = vol.Schema({ATTR_EVENT: _bytearray_string})

PLATFORMS = [
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.LIGHT,
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SIREN,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the RFXtrx component."""
    hass.data.setdefault(DOMAIN, {})

    try:
        await async_setup_internal(hass, entry)
    except asyncio.TimeoutError:
        # Library currently doesn't support reload
        _LOGGER.error(
            "Connection timeout: failed to receive response from RFXtrx device"
        )
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload RFXtrx component."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    hass.services.async_remove(DOMAIN, SERVICE_SEND)

    rfx_object = hass.data[DOMAIN][DATA_RFXOBJECT]
    await hass.async_add_executor_job(rfx_object.close_connection)

    hass.data.pop(DOMAIN)

    return True


def _create_rfx(config: Mapping[str, Any]) -> rfxtrxmod.Connect:
    """Construct a rfx object based on config."""

    modes = config.get(CONF_PROTOCOLS)

    if modes:
        _LOGGER.debug("Using modes: %s", ",".join(modes))
    else:
        _LOGGER.debug("No modes defined, using device configuration")

    if config[CONF_PORT] is not None:
        # If port is set then we create a TCP connection
        rfx = rfxtrxmod.Connect(
            (config[CONF_HOST], config[CONF_PORT]),
            None,
            transport_protocol=rfxtrxmod.PyNetworkTransport,
            modes=modes,
        )
    else:
        rfx = rfxtrxmod.Connect(
            config[CONF_DEVICE],
            None,
            modes=modes,
        )

    return rfx


def _get_device_lookup(
    devices: dict[str, dict[str, Any]]
) -> dict[DeviceTuple, dict[str, Any]]:
    """Get a lookup structure for devices."""
    lookup = {}
    for event_code, event_config in devices.items():
        if (event := get_rfx_object(event_code)) is None:
            continue
        device_id = get_device_id(
            event.device, data_bits=event_config.get(CONF_DATA_BITS)
        )
        lookup[device_id] = event_config
    return lookup


async def async_setup_internal(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the RFXtrx component."""
    config = entry.data

    # Initialize library
    async with async_timeout.timeout(30):
        rfx_object = await hass.async_add_executor_job(_create_rfx, config)

    # Setup some per device config
    devices = _get_device_lookup(config[CONF_DEVICES])
    pt2262_devices: list[str] = []

    device_registry = dr.async_get(hass)

    # Declare the Handle event
    @callback
    def async_handle_receive(event: rfxtrxmod.RFXtrxEvent) -> None:
        """Handle received messages from RFXtrx gateway."""
        # Log RFXCOM event
        if not event.device.id_string:
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
        device_id = get_device_id(event.device, data_bits=data_bits)

        if device_id not in devices:
            if config[CONF_AUTOMATIC_ADD]:
                _add_device(event, device_id)
            else:
                return

        if event.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            find_possible_pt2262_device(pt2262_devices, event.device.id_string)
            pt2262_devices.append(event.device.id_string)

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, *device_id)},  # type: ignore[arg-type]
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
        config = {}
        config[CONF_DEVICE_ID] = device_id

        _LOGGER.info(
            "Added device (Device ID: %s Class: %s Sub: %s, Event: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
            "".join(f"{x:02x}" for x in event.data),
        )

        data = entry.data.copy()
        data[CONF_DEVICES] = copy.deepcopy(entry.data[CONF_DEVICES])
        event_code = binascii.hexlify(event.data).decode("ASCII")
        data[CONF_DEVICES][event_code] = config
        hass.config_entries.async_update_entry(entry=entry, data=data)
        devices[device_id] = config

    @callback
    def _remove_device(device_id: DeviceTuple) -> None:
        data = {
            **entry.data,
            CONF_DEVICES: {
                packet_id: entity_info
                for packet_id, entity_info in entry.data[CONF_DEVICES].items()
                if tuple(entity_info.get(CONF_DEVICE_ID)) != device_id
            },
        }
        hass.config_entries.async_update_entry(entry=entry, data=data)
        devices.pop(device_id)

    @callback
    def _updated_device(event: Event) -> None:
        if event.data["action"] != "remove":
            return
        device_entry = device_registry.deleted_devices[event.data["device_id"]]
        if entry.entry_id not in device_entry.config_entries:
            return
        device_id = get_device_tuple_from_identifiers(device_entry.identifiers)
        if device_id:
            _remove_device(device_id)

    entry.async_on_unload(
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _updated_device)
    )

    def _shutdown_rfxtrx(event: Event) -> None:
        """Close connection with RFXtrx."""
        rfx_object.close_connection()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_rfxtrx)
    )
    hass.data[DOMAIN][DATA_RFXOBJECT] = rfx_object

    rfx_object.event_callback = lambda event: hass.add_job(async_handle_receive, event)

    def send(call: ServiceCall) -> None:
        event = call.data[ATTR_EVENT]
        rfx_object.transport.send(event)

    hass.services.async_register(DOMAIN, SERVICE_SEND, send, schema=SERVICE_SEND_SCHEMA)


async def async_setup_platform_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    supported: Callable[[rfxtrxmod.RFXtrxEvent], bool],
    constructor: Callable[
        [
            rfxtrxmod.RFXtrxEvent,
            rfxtrxmod.RFXtrxEvent | None,
            DeviceTuple,
            dict[str, Any],
        ],
        list[Entity],
    ],
) -> None:
    """Set up config entry."""
    entry_data = config_entry.data
    device_ids: set[DeviceTuple] = set()

    # Add entities from config
    entities = []
    for packet_id, entity_info in entry_data[CONF_DEVICES].items():
        if (event := get_rfx_object(packet_id)) is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        if not supported(event):
            continue

        device_id = get_device_id(
            event.device, data_bits=entity_info.get(CONF_DATA_BITS)
        )
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        entities.extend(constructor(event, None, device_id, entity_info))

    async_add_entities(entities)

    # If automatic add is on, hookup listener
    if entry_data[CONF_AUTOMATIC_ADD]:

        @callback
        def _update(event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple) -> None:
            """Handle light updates from the RFXtrx gateway."""
            if not supported(event):
                return

            if device_id in device_ids:
                return
            device_ids.add(device_id)
            async_add_entities(constructor(event, event, device_id, {}))

        config_entry.async_on_unload(
            async_dispatcher_connect(hass, SIGNAL_EVENT, _update)
        )


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
    device: rfxtrxmod.RFXtrxDevice, devices: dict[DeviceTuple, dict[str, Any]]
) -> int | None:
    """Deduce data bits for device based on a cache of device bits."""
    data_bits = None
    if device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
        for device_id, entity_config in devices.items():
            bits = entity_config.get(CONF_DATA_BITS)
            if get_device_id(device, bits) == device_id:
                data_bits = bits
                break
    return data_bits


def find_possible_pt2262_device(device_ids: list[str], device_id: str) -> str | None:
    """Look for the device which id matches the given device_id parameter."""
    for dev_id in device_ids:
        if len(dev_id) == len(device_id):
            size = None
            for i, (char1, char2) in enumerate(zip(dev_id, device_id)):
                if char1 != char2:
                    break
                size = i
            if size is not None:
                size = len(dev_id) - size - 1
                _LOGGER.info(
                    "Found possible device %s for %s "
                    "with the following configuration:\n"
                    "data_bits=%d\n"
                    "command_on=0x%s\n"
                    "command_off=0x%s\n",
                    device_id,
                    dev_id,
                    size * 4,
                    dev_id[-size:],
                    device_id[-size:],
                )
                return dev_id
    return None


def get_device_id(
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


def get_device_tuple_from_identifiers(
    identifiers: set[tuple[str, str]]
) -> DeviceTuple | None:
    """Calculate the device tuple from a device entry."""
    identifier = next((x for x in identifiers if x[0] == DOMAIN), None)
    if not identifier:
        return None
    # work around legacy identifier, being a multi tuple value
    identifier2 = cast(tuple[str, str, str, str], identifier)
    return DeviceTuple(identifier2[1], identifier2[2], identifier2[3])


def get_identifiers_from_device_tuple(
    device_tuple: DeviceTuple,
) -> set[tuple[str, str]]:
    """Calculate the device identifier from a device tuple."""
    # work around legacy identifier, being a multi tuple value
    return {(DOMAIN, *device_tuple)}  # type: ignore[arg-type]


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove config entry from a device.

    The actual cleanup is done in the device registry event
    """
    return True


class RfxtrxEntity(RestoreEntity):
    """Represents a Rfxtrx device.

    Contains the common logic for Rfxtrx lights and switches.
    """

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_should_poll = False
    _device: rfxtrxmod.RFXtrxDevice
    _event: rfxtrxmod.RFXtrxEvent | None

    def __init__(
        self,
        device: rfxtrxmod.RFXtrxDevice,
        device_id: DeviceTuple,
        event: rfxtrxmod.RFXtrxEvent | None = None,
    ) -> None:
        """Initialize the device."""
        self._attr_device_info = DeviceInfo(
            identifiers=get_identifiers_from_device_tuple(device_id),
            model=device.type_string,
            name=f"{device.type_string} {device.id_string}",
        )
        self._attr_unique_id = "_".join(x for x in device_id)
        self._device = device
        self._event = event
        self._device_id = device_id
        # If id_string is 213c7f2:1, the group_id is 213c7f2, and the device will respond to
        # group events regardless of their group indices.
        (self._group_id, _, _) = cast(str, device.id_string).partition(":")

    async def async_added_to_hass(self) -> None:
        """Restore RFXtrx device state (ON/OFF)."""
        if self._event:
            self._apply_event(self._event)

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_EVENT, self._handle_event)
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the device state attributes."""
        if not self._event:
            return None
        return {ATTR_EVENT: "".join(f"{x:02x}" for x in self._event.data)}

    def _event_applies(
        self, event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple
    ) -> bool:
        """Check if event applies to me."""
        if isinstance(event, rfxtrxmod.ControlEvent):
            if (
                "Command" in event.values
                and event.values["Command"] in COMMAND_GROUP_LIST
            ):
                device: rfxtrxmod.RFXtrxDevice = event.device
                (group_id, _, _) = cast(str, device.id_string).partition(":")
                return group_id == self._group_id

        # Otherwise, the event only applies to the matching device.
        return device_id == self._device_id

    def _apply_event(self, event: rfxtrxmod.RFXtrxEvent) -> None:
        """Apply a received event."""
        self._event = event

    @callback
    def _handle_event(
        self, event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple
    ) -> None:
        """Handle a reception of data, overridden by other classes."""


class RfxtrxCommandEntity(RfxtrxEntity):
    """Represents a Rfxtrx device.

    Contains the common logic for Rfxtrx lights and switches.
    """

    def __init__(
        self,
        device: rfxtrxmod.RFXtrxDevice,
        device_id: DeviceTuple,
        event: rfxtrxmod.RFXtrxEvent | None = None,
    ) -> None:
        """Initialzie a switch or light device."""
        super().__init__(device, device_id, event=event)

    async def _async_send(self, fun: Callable[..., None], *args: Any) -> None:
        rfx_object = self.hass.data[DOMAIN][DATA_RFXOBJECT]
        await self.hass.async_add_executor_job(fun, rfx_object.transport, *args)
