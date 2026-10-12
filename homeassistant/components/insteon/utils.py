"""Utilities used by insteon component."""

import asyncio
from collections.abc import Callable
from functools import partial
import logging
from typing import TYPE_CHECKING, Any

from pyinsteon import devices
from pyinsteon.address import Address
from pyinsteon.constants import ALDBStatus, DeviceAction
from pyinsteon.device_types.device_base import Device
from pyinsteon.events import OFF_EVENT, OFF_FAST_EVENT, ON_EVENT, ON_FAST_EVENT, Event
from pyinsteon.x10_address import create as create_x10_address

from homeassistant.components import usb
from homeassistant.const import CONF_ADDRESS, CONF_PLATFORM, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
    dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_CAT,
    CONF_DIM_STEPS,
    CONF_HOUSECODE,
    CONF_SUBCAT,
    CONF_UNITCODE,
    DOMAIN,
    EVENT_CONF_BUTTON,
    EVENT_GROUP_OFF,
    EVENT_GROUP_OFF_FAST,
    EVENT_GROUP_ON,
    EVENT_GROUP_ON_FAST,
    SIGNAL_ADD_DEVICE_OVERRIDE,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ADD_X10_DEVICE,
    SIGNAL_REMOVE_DEVICE_OVERRIDE,
    SIGNAL_REMOVE_ENTITY,
    SIGNAL_REMOVE_HA_DEVICE,
    SIGNAL_REMOVE_INSTEON_DEVICE,
    SIGNAL_REMOVE_X10_DEVICE,
    SIGNAL_SAVE_DEVICES,
)
from .ipdb import get_device_platform_groups, get_device_platforms

if TYPE_CHECKING:
    from .entity import InsteonEntity

_LOGGER = logging.getLogger(__name__)

_DATA_SAVE_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_save_lock")


def _register_event(event: Event, listener: Callable) -> None:
    """Register the events raised by a device."""
    _LOGGER.debug(
        "Registering on/off event for %s %d %s",
        str(event.address),
        event.group,
        event.name,
    )
    event.subscribe(listener, force_strong_ref=True)


def add_insteon_events(hass: HomeAssistant, device: Device) -> None:
    """Register Insteon device events."""

    @callback
    def async_fire_insteon_event(
        name: str, address: Address, group: int, button: str | None = None
    ):
        # Firing an event when a button is pressed.
        if button and button[-2] == "_":
            button_id = button[-1].lower()
        else:
            button_id = None

        schema = {CONF_ADDRESS: address, "group": group}
        if button_id:
            schema[EVENT_CONF_BUTTON] = button_id
        if name == ON_EVENT:
            event = EVENT_GROUP_ON
        elif name == OFF_EVENT:
            event = EVENT_GROUP_OFF
        elif name == ON_FAST_EVENT:
            event = EVENT_GROUP_ON_FAST
        elif name == OFF_FAST_EVENT:
            event = EVENT_GROUP_OFF_FAST
        else:
            event = f"insteon.{name}"
        _LOGGER.debug("Firing event %s with %s", event, schema)
        hass.bus.async_fire(event, schema)

    if str(device.address).startswith("X10"):
        return

    for name_or_group, event in device.events.items():
        if isinstance(name_or_group, int):
            for event in device.events[name_or_group].values():
                _register_event(event, async_fire_insteon_event)
        else:
            _register_event(event, async_fire_insteon_event)


def register_new_device_callback(hass: HomeAssistant) -> None:
    """Register callback for new Insteon device."""

    @callback
    def async_new_insteon_device(address, action: DeviceAction):
        """Detect device from transport to be delegated to platform."""
        if action == DeviceAction.ADDED:
            hass.async_create_task(async_create_new_entities(address))

    async def async_create_new_entities(address):
        _LOGGER.debug(
            "Adding new INSTEON device to Home Assistant with address %s", address
        )
        await devices.async_save(workdir=hass.config.config_dir)
        device = devices[address]
        await device.async_status()
        platforms = get_device_platforms(device)
        for platform in platforms:
            groups = get_device_platform_groups(device, platform)
            signal = f"{SIGNAL_ADD_ENTITIES}_{platform}"
            dispatcher_send(hass, signal, {"address": device.address, "groups": groups})
        add_insteon_events(hass, device)

    devices.subscribe(async_new_insteon_device, force_strong_ref=True)


def print_aldb_to_log(aldb):
    """Print the All-Link Database to the log file."""
    logger = logging.getLogger(f"{__name__}.links")
    logger.info("%s ALDB load status is %s", aldb.address, aldb.status.name)
    if aldb.status not in [ALDBStatus.LOADED, ALDBStatus.PARTIAL]:
        _LOGGER.warning("All-Link database not loaded")

    logger.info("RecID In Use Mode HWM Group Address  Data 1 Data 2 Data 3")
    logger.info("----- ------ ---- --- ----- -------- ------ ------ ------")
    for mem_addr in aldb:
        rec = aldb[mem_addr]
        # For now we write this to the log
        # Roadmap is to create a configuration panel
        in_use = "Y" if rec.is_in_use else "N"
        mode = "C" if rec.is_controller else "R"
        hwm = "Y" if rec.is_high_water_mark else "N"
        log_msg = (
            f" {rec.mem_addr:04x}    {in_use:s}     {mode:s}   {hwm:s}    "
            f"{rec.group:3d} {rec.target!s:s}   {rec.data1:3d}   "
            f"{rec.data2:3d}   {rec.data3:3d}"
        )
        logger.info(log_msg)


@callback
def async_add_insteon_entities(
    hass: HomeAssistant,
    platform: Platform,
    entity_type: type[InsteonEntity],
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: dict[str, Any],
) -> None:
    """Add an Insteon group to a platform."""
    address = discovery_info["address"]
    device = devices[address]
    new_entities = [
        entity_type(device=device, group=group) for group in discovery_info["groups"]
    ]
    async_add_entities(new_entities)


@callback
def async_add_insteon_devices(
    hass: HomeAssistant,
    platform: Platform,
    entity_type: type[InsteonEntity],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add all entities to a platform."""
    for address in devices:
        device = devices[address]
        groups = get_device_platform_groups(device, platform)
        discovery_info = {"address": address, "groups": groups}
        async_add_insteon_entities(
            hass, platform, entity_type, async_add_entities, discovery_info
        )


async def async_get_usb_ports(hass: HomeAssistant) -> dict[str, str]:
    """Return a dict of USB ports and their friendly names."""
    port_descriptions = {}
    for port in await usb.async_scan_serial_ports(hass):
        human_name = usb.human_readable_device_name(
            port.device,
            port.serial_number,
            port.manufacturer,
            port.description,
            port.vid if isinstance(port, usb.USBDevice) else None,
            port.pid if isinstance(port, usb.USBDevice) else None,
        )
        port_descriptions[port.device] = human_name
    return port_descriptions


def compute_device_name(ha_device) -> str:
    """Return the HA device name."""
    return ha_device.name_by_user or ha_device.name


async def async_device_name(
    dev_registry: dr.DeviceRegistry, address: Address, config_entry_id: str
) -> str:
    """Get the Insteon device name from a device registry id."""
    ha_device = dev_registry.async_get_device_by_identifier(
        (DOMAIN, str(address)), config_entry_id
    )
    if not ha_device:
        if device := devices[address]:
            return f"{device.description} ({device.model})"
        return ""
    return compute_device_name(ha_device)


@singleton(_DATA_SAVE_LOCK)
@callback
def _async_get_save_lock(hass: HomeAssistant) -> asyncio.Lock:
    """Return the lock serializing writes of the Insteon device configuration."""
    return asyncio.Lock()


async def async_save_devices(hass: HomeAssistant) -> None:
    """Write the Insteon device configuration to file."""
    async with _async_get_save_lock(hass):
        _LOGGER.debug("Saving Insteon devices")
        await devices.async_save(hass.config.config_dir)


async def _async_add_device_override(
    hass: HomeAssistant, override: dict[str, Any]
) -> None:
    """Remove an Insten device and associated entities."""
    address = Address(override[CONF_ADDRESS])
    await _async_remove_ha_device(hass, address)
    devices.set_id(address, override[CONF_CAT], override[CONF_SUBCAT], 0)
    await async_save_devices(hass)


async def _async_remove_device_override(hass: HomeAssistant, address: str) -> None:
    """Remove an Insten device and associated entities."""
    insteon_address = Address(address)
    await _async_remove_ha_device(hass, insteon_address)
    devices.set_id(insteon_address, None, None, None)
    await devices.async_identify_device(insteon_address)
    await async_save_devices(hass)


@callback
def _async_add_x10_device(hass: HomeAssistant, x10_config: dict[str, Any]) -> None:
    """Add X10 device."""
    housecode = x10_config[CONF_HOUSECODE]
    unitcode = x10_config[CONF_UNITCODE]
    platform = x10_config[CONF_PLATFORM]
    steps = x10_config.get(CONF_DIM_STEPS, 22)
    x10_type = "on_off"
    if platform == "light":
        x10_type = "dimmable"
    elif platform == "binary_sensor":
        x10_type = "sensor"
    _LOGGER.debug(
        "Adding X10 device to Insteon: %s %d %s", housecode, unitcode, x10_type
    )
    # This must be run in the event loop
    devices.add_x10_device(housecode, unitcode, x10_type, steps)


async def _async_remove_x10_device(
    hass: HomeAssistant, housecode: str, unitcode: int
) -> None:
    """Remove an X10 device and associated entities."""
    address = create_x10_address(housecode, unitcode)
    devices.pop(address)
    await _async_remove_ha_device(hass, address)


async def _async_remove_ha_device(
    hass: HomeAssistant, address: Address, remove_all_refs: bool = False
) -> None:
    """Remove the device and all entities from hass."""
    signal = f"{address.id}_{SIGNAL_REMOVE_ENTITY}"
    async_dispatcher_send(hass, signal)
    dev_registry = dr.async_get(hass)
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = dev_registry.async_get_device_by_identifier(
        (DOMAIN, str(address)), config_entry.entry_id
    )
    if device:
        dev_registry.async_remove_device(device.id)


async def _async_remove_insteon_device(
    hass: HomeAssistant, address: Address, remove_all_refs: bool = False
) -> None:
    """Remove the underlying Insteon device from the network."""
    await devices.async_remove_device(
        address=address, force=False, remove_all_refs=remove_all_refs
    )
    await async_save_devices(hass)


@callback
def async_connect_device_signals(hass: HomeAssistant) -> list[CALLBACK_TYPE]:
    """Connect the dispatcher signals used to manage Insteon devices."""
    return [
        async_dispatcher_connect(hass, signal, partial(target, hass))
        for signal, target in (
            (SIGNAL_SAVE_DEVICES, async_save_devices),
            (SIGNAL_ADD_DEVICE_OVERRIDE, _async_add_device_override),
            (SIGNAL_REMOVE_DEVICE_OVERRIDE, _async_remove_device_override),
            (SIGNAL_ADD_X10_DEVICE, _async_add_x10_device),
            (SIGNAL_REMOVE_X10_DEVICE, _async_remove_x10_device),
            (SIGNAL_REMOVE_HA_DEVICE, _async_remove_ha_device),
            (SIGNAL_REMOVE_INSTEON_DEVICE, _async_remove_insteon_device),
        )
    ]
