"""Utilities used by insteon component."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

from pyinsteon import devices
from pyinsteon.address import Address
from pyinsteon.constants import ALDBStatus, DeviceAction
from pyinsteon.device_types.device_base import Device
from pyinsteon.events import OFF_EVENT, OFF_FAST_EVENT, ON_EVENT, ON_FAST_EVENT, Event
from serial.tools import list_ports

from homeassistant.components import usb
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    EVENT_CONF_BUTTON,
    EVENT_GROUP_OFF,
    EVENT_GROUP_OFF_FAST,
    EVENT_GROUP_ON,
    EVENT_GROUP_ON_FAST,
    SIGNAL_ADD_ENTITIES,
)
from .ipdb import get_device_platform_groups, get_device_platforms

if TYPE_CHECKING:
    from .entity import InsteonEntity

_LOGGER = logging.getLogger(__name__)


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


def get_usb_ports() -> dict[str, str]:
    """Return a dict of USB ports and their friendly names."""
    ports = list_ports.comports()
    port_descriptions = {}
    for port in ports:
        vid: str | None = None
        pid: str | None = None
        if port.vid is not None and port.pid is not None:
            usb_device = usb.usb_device_from_port(port)
            vid = usb_device.vid
            pid = usb_device.pid
        dev_path = usb.get_serial_by_id(port.device)
        human_name = usb.human_readable_device_name(
            dev_path,
            port.serial_number,
            port.manufacturer,
            port.description,
            vid,
            pid,
        )
        port_descriptions[dev_path] = human_name
    return port_descriptions


async def async_get_usb_ports(hass: HomeAssistant) -> dict[str, str]:
    """Return a dict of USB ports and their friendly names."""
    return await hass.async_add_executor_job(get_usb_ports)


def compute_device_name(ha_device) -> str:
    """Return the HA device name."""
    return ha_device.name_by_user if ha_device.name_by_user else ha_device.name


async def async_device_name(dev_registry: dr.DeviceRegistry, address: Address) -> str:
    """Get the Insteon device name from a device registry id."""
    ha_device = dev_registry.async_get_device(identifiers={(DOMAIN, str(address))})
    if not ha_device:
        if device := devices[address]:
            return f"{device.description} ({device.model})"
        return ""
    return compute_device_name(ha_device)
