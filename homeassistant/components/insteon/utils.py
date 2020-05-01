"""Utilities used by insteon component."""

import logging

from pyinsteon import devices
from pyinsteon.constants import ALDBStatus
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

from homeassistant.const import CONF_ADDRESS, CONF_ENTITY_ID, ENTITY_MATCH_ALL
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send

from .const import (
    DOMAIN,
    EVENT_CONF_BUTTON,
    EVENT_GROUP_OFF,
    EVENT_GROUP_OFF_FAST,
    EVENT_GROUP_ON,
    EVENT_GROUP_ON_FAST,
    ON_OFF_EVENTS,
    SIGNAL_LOAD_ALDB,
    SIGNAL_PRINT_ALDB,
    SIGNAL_SAVE_DEVICES,
    SRV_ADD_ALL_LINK,
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
        hass.bus.fire(event, schema)

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


def register_new_device_callback(hass, config):
    """Register callback for new Insteon device."""

    @callback
    def async_new_insteon_device(address=None):
        """Detect device from transport to be delegated to platform."""
        _LOGGER.info(
            "Adding new INSTEON device to Home Assistant with address %s", address
        )
        hass.async_add_job(devices.async_save, hass.config.config_dir)
        device = devices[address]
        device.status()
        platforms = get_device_platforms(device)
        for platform in platforms:
            if platform == ON_OFF_EVENTS:
                add_on_off_event_device(hass, device)

            else:
                hass.async_create_task(
                    discovery.async_load_platform(
                        hass,
                        platform,
                        DOMAIN,
                        discovered={"address": device.address.id},
                        hass_config=config,
                    )
                )

    devices.subscribe(async_new_insteon_device, force_strong_ref=True)


@callback
def async_register_services(hass):
    """Register services used by insteon component."""

    def add_all_link(service):
        """Add an INSTEON All-Link between two devices."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        mode = service.data.get(SRV_ALL_LINK_MODE)
        link_mode = mode.lower() == SRV_CONTROLLER
        hass.async_add_job(async_enter_linking_mode, link_mode, group)

    def del_all_link(service):
        """Delete an INSTEON All-Link between two devices."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        hass.async_add_job(async_enter_unlinking_mode, group)

    def load_aldb(service):
        """Load the device All-Link database."""
        entity_id = service.data[CONF_ENTITY_ID]
        reload = service.data[SRV_LOAD_DB_RELOAD]
        if entity_id.lower() == ENTITY_MATCH_ALL:
            hass.async_add_job(_load_aldb_all, reload)
        else:
            _send_load_aldb_signal(entity_id, reload)

    def _send_load_aldb_signal(entity_id, reload):
        """Send the load All-Link database signal to INSTEON entity."""
        signal = f"{entity_id}_{SIGNAL_LOAD_ALDB}"
        dispatcher_send(hass, signal, hass.async_add_job, reload)

    async def _load_aldb_all(reload):
        """Load the All-Link database for all devices."""
        for address in devices:
            device = devices[address]
            if device != devices.modem and device.cat != 0x03:
                await device.aldb.async_load(refresh=reload, callback=_save_devices)

    def _save_devices():
        """Write the Insteon device configuration to file."""
        _LOGGER.debug("Saving Insteon devices")
        hass.async_add_job(devices.async_save, hass.config.config_dir)

    def print_aldb(service):
        """Print the All-Link Database for a device."""
        # For now this sends logs to the log file.
        # Future direction is to create an INSTEON control panel.
        entity_id = service.data[CONF_ENTITY_ID]
        signal = f"{entity_id}_{SIGNAL_PRINT_ALDB}"
        dispatcher_send(hass, signal)

    def print_im_aldb(service):
        """Print the All-Link Database for a device."""
        # For now this sends logs to the log file.
        # Future direction is to create an INSTEON control panel.
        print_aldb_to_log(devices.modem.aldb)

    def x10_all_units_off(service):
        """Send the X10 All Units Off command."""
        housecode = service.data.get(SRV_HOUSECODE)
        hass.async_add_job(async_x10_all_units_off, housecode)

    def x10_all_lights_off(service):
        """Send the X10 All Lights Off command."""
        housecode = service.data.get(SRV_HOUSECODE)
        hass.async_add_job(async_x10_all_lights_off, housecode)

    def x10_all_lights_on(service):
        """Send the X10 All Lights On command."""
        housecode = service.data.get(SRV_HOUSECODE)
        hass.async_add_job(async_x10_all_lights_on, housecode)

    def scene_on(service):
        """Trigger an INSTEON scene ON."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        hass.async_add_job(async_trigger_scene_on, group)

    def scene_off(service):
        """Trigger an INSTEON scene ON."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        hass.async_add_job(async_trigger_scene_off, group)

    hass.services.async_register(
        DOMAIN, SRV_ADD_ALL_LINK, add_all_link, schema=ADD_ALL_LINK_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_DEL_ALL_LINK, del_all_link, schema=DEL_ALL_LINK_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_LOAD_ALDB, load_aldb, schema=LOAD_ALDB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_PRINT_ALDB, print_aldb, schema=PRINT_ALDB_SCHEMA
    )
    hass.services.async_register(DOMAIN, SRV_PRINT_IM_ALDB, print_im_aldb, schema=None)
    hass.services.async_register(
        DOMAIN, SRV_X10_ALL_UNITS_OFF, x10_all_units_off, schema=X10_HOUSECODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_X10_ALL_LIGHTS_OFF, x10_all_lights_off, schema=X10_HOUSECODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_X10_ALL_LIGHTS_ON, x10_all_lights_on, schema=X10_HOUSECODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_SCENE_ON, scene_on, schema=TRIGGER_SCENE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_SCENE_OFF, scene_off, schema=TRIGGER_SCENE_SCHEMA
    )
    async_dispatcher_connect(hass, SIGNAL_SAVE_DEVICES, _save_devices)
    _LOGGER.debug("Insteon Services registered")


def print_aldb_to_log(aldb):
    """Print the All-Link Database to the log file."""
    # This service is useless if the log level is not INFO for the
    # insteon component. Setting the log level to INFO and resetting it
    # back when we are done
    orig_log_level = _LOGGER.level
    if orig_log_level > logging.INFO:
        _LOGGER.setLevel(logging.INFO)
    _LOGGER.info("ALDB load status is %s", aldb.status.name)
    if aldb.status not in [ALDBStatus.LOADED, ALDBStatus.PARTIAL]:
        _LOGGER.warning("Device All-Link database not loaded")
        _LOGGER.warning("Use service insteon.load_aldb first")
        return

    _LOGGER.info("RecID In Use Mode HWM Group Address  Data 1 Data 2 Data 3")
    _LOGGER.info("----- ------ ---- --- ----- -------- ------ ------ ------")
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
        _LOGGER.info(log_msg)
    _LOGGER.setLevel(orig_log_level)


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
            _LOGGER.debug(
                "Adding device %s group %s to %s platform",
                device.address,
                group,
                platform,
            )
            new_entities.append(entity_type(device, group))
    if new_entities:
        async_add_entities(new_entities)
