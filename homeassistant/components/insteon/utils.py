"""Utilities used by insteon component."""
import asyncio
import logging

from pyinsteon import devices
from pyinsteon.address import Address
from pyinsteon.constants import ALDBStatus, DeviceAction
from pyinsteon.events import OFF_EVENT, OFF_FAST_EVENT, ON_EVENT, ON_FAST_EVENT
from pyinsteon.managers.link_manager import (
    async_enter_linking_mode,
    async_enter_unlinking_mode,
)
from pyinsteon.managers.scene_manager import (
    async_trigger_scene_off,
    async_trigger_scene_on,
)
from pyinsteon.managers.x10_manager import (
    async_x10_all_lights_off,
    async_x10_all_lights_on,
    async_x10_all_units_off,
)
from pyinsteon.x10_address import create as create_x10_address

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    ENTITY_MATCH_ALL,
)
from homeassistant.core import ServiceCall, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
    dispatcher_send,
)

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
    ON_OFF_EVENTS,
    SIGNAL_ADD_DEFAULT_LINKS,
    SIGNAL_ADD_DEVICE_OVERRIDE,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ADD_X10_DEVICE,
    SIGNAL_LOAD_ALDB,
    SIGNAL_PRINT_ALDB,
    SIGNAL_REMOVE_DEVICE_OVERRIDE,
    SIGNAL_REMOVE_ENTITY,
    SIGNAL_REMOVE_X10_DEVICE,
    SIGNAL_SAVE_DEVICES,
    SRV_ADD_ALL_LINK,
    SRV_ADD_DEFAULT_LINKS,
    SRV_ALL_LINK_GROUP,
    SRV_ALL_LINK_MODE,
    SRV_CONTROLLER,
    SRV_DEL_ALL_LINK,
    SRV_HOUSECODE,
    SRV_LOAD_ALDB,
    SRV_LOAD_DB_RELOAD,
    SRV_PRINT_ALDB,
    SRV_PRINT_IM_ALDB,
    SRV_SCENE_OFF,
    SRV_SCENE_ON,
    SRV_X10_ALL_LIGHTS_OFF,
    SRV_X10_ALL_LIGHTS_ON,
    SRV_X10_ALL_UNITS_OFF,
)
from .ipdb import get_device_platforms, get_platform_groups
from .schemas import (
    ADD_ALL_LINK_SCHEMA,
    ADD_DEFAULT_LINKS_SCHEMA,
    DEL_ALL_LINK_SCHEMA,
    LOAD_ALDB_SCHEMA,
    PRINT_ALDB_SCHEMA,
    TRIGGER_SCENE_SCHEMA,
    X10_HOUSECODE_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)


def add_on_off_event_device(hass, device):
    """Register an Insteon device as an on/off event device."""

    @callback
    def async_fire_group_on_off_event(name, address, group, button):
        # Firing an event when a button is pressed.
        if button and button[-2] == "_":
            button_id = button[-1].lower()
        else:
            button_id = None

        schema = {CONF_ADDRESS: address}
        if button_id:
            schema[EVENT_CONF_BUTTON] = button_id
        if name == ON_EVENT:
            event = EVENT_GROUP_ON
        if name == OFF_EVENT:
            event = EVENT_GROUP_OFF
        if name == ON_FAST_EVENT:
            event = EVENT_GROUP_ON_FAST
        if name == OFF_FAST_EVENT:
            event = EVENT_GROUP_OFF_FAST
        _LOGGER.debug("Firing event %s with %s", event, schema)
        hass.bus.async_fire(event, schema)

    for group in device.events:
        if isinstance(group, int):
            for event in device.events[group]:
                if event in [
                    OFF_EVENT,
                    ON_EVENT,
                    OFF_FAST_EVENT,
                    ON_FAST_EVENT,
                ]:
                    _LOGGER.debug(
                        "Registering on/off event for %s %d %s",
                        str(device.address),
                        group,
                        event,
                    )
                    device.events[group][event].subscribe(
                        async_fire_group_on_off_event, force_strong_ref=True
                    )


def register_new_device_callback(hass):
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
            if platform == ON_OFF_EVENTS:
                add_on_off_event_device(hass, device)

            else:
                signal = f"{SIGNAL_ADD_ENTITIES}_{platform}"
                dispatcher_send(hass, signal, {"address": device.address})

    devices.subscribe(async_new_insteon_device, force_strong_ref=True)


@callback
def async_register_services(hass):
    """Register services used by insteon component."""

    save_lock = asyncio.Lock()

    async def async_srv_add_all_link(service: ServiceCall) -> None:
        """Add an INSTEON All-Link between two devices."""
        group = service.data[SRV_ALL_LINK_GROUP]
        mode = service.data[SRV_ALL_LINK_MODE]
        link_mode = mode.lower() == SRV_CONTROLLER
        await async_enter_linking_mode(link_mode, group)

    async def async_srv_del_all_link(service: ServiceCall) -> None:
        """Delete an INSTEON All-Link between two devices."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        await async_enter_unlinking_mode(group)

    async def async_srv_load_aldb(service: ServiceCall) -> None:
        """Load the device All-Link database."""
        entity_id = service.data[CONF_ENTITY_ID]
        reload = service.data[SRV_LOAD_DB_RELOAD]
        if entity_id.lower() == ENTITY_MATCH_ALL:
            await async_srv_load_aldb_all(reload)
        else:
            signal = f"{entity_id}_{SIGNAL_LOAD_ALDB}"
            async_dispatcher_send(hass, signal, reload)

    async def async_srv_load_aldb_all(reload):
        """Load the All-Link database for all devices."""
        # Cannot be done concurrently due to issues with the underlying protocol.
        for address in devices:
            device = devices[address]
            if device != devices.modem and device.cat != 0x03:
                await device.aldb.async_load(refresh=reload)
                await async_srv_save_devices()

    async def async_srv_save_devices():
        """Write the Insteon device configuration to file."""
        async with save_lock:
            _LOGGER.debug("Saving Insteon devices")
            await devices.async_save(hass.config.config_dir)

    def print_aldb(service: ServiceCall) -> None:
        """Print the All-Link Database for a device."""
        # For now this sends logs to the log file.
        # Future direction is to create an INSTEON control panel.
        entity_id = service.data[CONF_ENTITY_ID]
        signal = f"{entity_id}_{SIGNAL_PRINT_ALDB}"
        dispatcher_send(hass, signal)

    def print_im_aldb(service: ServiceCall) -> None:
        """Print the All-Link Database for a device."""
        # For now this sends logs to the log file.
        # Future direction is to create an INSTEON control panel.
        print_aldb_to_log(devices.modem.aldb)

    async def async_srv_x10_all_units_off(service: ServiceCall) -> None:
        """Send the X10 All Units Off command."""
        housecode = service.data.get(SRV_HOUSECODE)
        await async_x10_all_units_off(housecode)

    async def async_srv_x10_all_lights_off(service: ServiceCall) -> None:
        """Send the X10 All Lights Off command."""
        housecode = service.data.get(SRV_HOUSECODE)
        await async_x10_all_lights_off(housecode)

    async def async_srv_x10_all_lights_on(service: ServiceCall) -> None:
        """Send the X10 All Lights On command."""
        housecode = service.data.get(SRV_HOUSECODE)
        await async_x10_all_lights_on(housecode)

    async def async_srv_scene_on(service: ServiceCall) -> None:
        """Trigger an INSTEON scene ON."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        await async_trigger_scene_on(group)

    async def async_srv_scene_off(service: ServiceCall) -> None:
        """Trigger an INSTEON scene ON."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        await async_trigger_scene_off(group)

    @callback
    def async_add_default_links(service: ServiceCall) -> None:
        """Add the default All-Link entries to a device."""
        entity_id = service.data[CONF_ENTITY_ID]
        signal = f"{entity_id}_{SIGNAL_ADD_DEFAULT_LINKS}"
        async_dispatcher_send(hass, signal)

    async def async_add_device_override(override):
        """Remove an Insten device and associated entities."""
        address = Address(override[CONF_ADDRESS])
        await async_remove_device(address)
        devices.set_id(address, override[CONF_CAT], override[CONF_SUBCAT], 0)
        await async_srv_save_devices()

    async def async_remove_device_override(address):
        """Remove an Insten device and associated entities."""
        address = Address(address)
        await async_remove_device(address)
        devices.set_id(address, None, None, None)
        await devices.async_identify_device(address)
        await async_srv_save_devices()

    @callback
    def async_add_x10_device(x10_config):
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

    async def async_remove_x10_device(housecode, unitcode):
        """Remove an X10 device and associated entities."""
        address = create_x10_address(housecode, unitcode)
        devices.pop(address)
        await async_remove_device(address)

    async def async_remove_device(address):
        """Remove the device and all entities from hass."""
        signal = f"{address.id}_{SIGNAL_REMOVE_ENTITY}"
        async_dispatcher_send(hass, signal)
        dev_registry = dr.async_get(hass)
        device = dev_registry.async_get_device(identifiers={(DOMAIN, str(address))})
        if device:
            dev_registry.async_remove_device(device.id)

    hass.services.async_register(
        DOMAIN, SRV_ADD_ALL_LINK, async_srv_add_all_link, schema=ADD_ALL_LINK_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_DEL_ALL_LINK, async_srv_del_all_link, schema=DEL_ALL_LINK_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_LOAD_ALDB, async_srv_load_aldb, schema=LOAD_ALDB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_PRINT_ALDB, print_aldb, schema=PRINT_ALDB_SCHEMA
    )
    hass.services.async_register(DOMAIN, SRV_PRINT_IM_ALDB, print_im_aldb, schema=None)
    hass.services.async_register(
        DOMAIN,
        SRV_X10_ALL_UNITS_OFF,
        async_srv_x10_all_units_off,
        schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SRV_X10_ALL_LIGHTS_OFF,
        async_srv_x10_all_lights_off,
        schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SRV_X10_ALL_LIGHTS_ON,
        async_srv_x10_all_lights_on,
        schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SRV_SCENE_ON, async_srv_scene_on, schema=TRIGGER_SCENE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_SCENE_OFF, async_srv_scene_off, schema=TRIGGER_SCENE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SRV_ADD_DEFAULT_LINKS,
        async_add_default_links,
        schema=ADD_DEFAULT_LINKS_SCHEMA,
    )
    async_dispatcher_connect(hass, SIGNAL_SAVE_DEVICES, async_srv_save_devices)
    async_dispatcher_connect(
        hass, SIGNAL_ADD_DEVICE_OVERRIDE, async_add_device_override
    )
    async_dispatcher_connect(
        hass, SIGNAL_REMOVE_DEVICE_OVERRIDE, async_remove_device_override
    )
    async_dispatcher_connect(hass, SIGNAL_ADD_X10_DEVICE, async_add_x10_device)
    async_dispatcher_connect(hass, SIGNAL_REMOVE_X10_DEVICE, async_remove_x10_device)
    _LOGGER.debug("Insteon Services registered")


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
            f"{rec.group:3d} {str(rec.target):s}   {rec.data1:3d}   "
            f"{rec.data2:3d}   {rec.data3:3d}"
        )
        logger.info(log_msg)


@callback
def async_add_insteon_entities(
    hass, platform, entity_type, async_add_entities, discovery_info
):
    """Add Insteon devices to a platform."""
    new_entities = []
    device_list = [discovery_info.get("address")] if discovery_info else devices

    for address in device_list:
        device = devices[address]
        groups = get_platform_groups(device, platform)
        for group in groups:
            new_entities.append(entity_type(device, group))
    async_add_entities(new_entities)
