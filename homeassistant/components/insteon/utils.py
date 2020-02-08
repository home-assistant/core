"""Utilities used by insteon component."""

import logging

from insteonplm.devices import ALDBStatus

from homeassistant.const import CONF_ADDRESS, CONF_ENTITY_ID, ENTITY_MATCH_ALL
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    BUTTON_PRESSED_STATE_NAME,
    DOMAIN,
    EVENT_BUTTON_OFF,
    EVENT_BUTTON_ON,
    EVENT_CONF_BUTTON,
    INSTEON_ENTITIES,
    SIGNAL_LOAD_ALDB,
    SIGNAL_PRINT_ALDB,
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
from .ipdb import IPDB
from .schemas import (
    ADD_ALL_LINK_SCHEMA,
    DEL_ALL_LINK_SCHEMA,
    LOAD_ALDB_SCHEMA,
    PRINT_ALDB_SCHEMA,
    TRIGGER_SCENE_SCHEMA,
    X10_HOUSECODE_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)


def register_new_device_callback(hass, config, insteon_modem):
    """Register callback for new Insteon device."""

    def _fire_button_on_off_event(address, group, val):
        # Firing an event when a button is pressed.
        device = insteon_modem.devices[address.hex]
        state_name = device.states[group].name
        button = (
            "" if state_name == BUTTON_PRESSED_STATE_NAME else state_name[-1].lower()
        )
        schema = {CONF_ADDRESS: address.hex}
        if button != "":
            schema[EVENT_CONF_BUTTON] = button
        if val:
            event = EVENT_BUTTON_ON
        else:
            event = EVENT_BUTTON_OFF
        _LOGGER.debug(
            "Firing event %s with address %s and button %s", event, address.hex, button
        )
        hass.bus.fire(event, schema)

    @callback
    def async_new_insteon_device(device):
        """Detect device from transport to be delegated to platform."""
        ipdb = IPDB()
        for state_key in device.states:
            platform_info = ipdb[device.states[state_key]]
            if platform_info and platform_info.platform:
                platform = platform_info.platform

                if platform == "on_off_events":
                    device.states[state_key].register_updates(_fire_button_on_off_event)

                else:
                    _LOGGER.info(
                        "New INSTEON device: %s (%s) %s",
                        device.address,
                        device.states[state_key].name,
                        platform,
                    )

                    hass.async_create_task(
                        discovery.async_load_platform(
                            hass,
                            platform,
                            DOMAIN,
                            discovered={
                                "address": device.address.id,
                                "state_key": state_key,
                            },
                            hass_config=config,
                        )
                    )

    insteon_modem.devices.add_device_callback(async_new_insteon_device)


@callback
def async_register_services(hass, config, insteon_modem):
    """Register services used by insteon component."""

    def add_all_link(service):
        """Add an INSTEON All-Link between two devices."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        mode = service.data.get(SRV_ALL_LINK_MODE)
        link_mode = 1 if mode.lower() == SRV_CONTROLLER else 0
        insteon_modem.start_all_linking(link_mode, group)

    def del_all_link(service):
        """Delete an INSTEON All-Link between two devices."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        insteon_modem.start_all_linking(255, group)

    def load_aldb(service):
        """Load the device All-Link database."""
        entity_id = service.data[CONF_ENTITY_ID]
        reload = service.data[SRV_LOAD_DB_RELOAD]
        if entity_id.lower() == ENTITY_MATCH_ALL:
            for entity_id in hass.data[DOMAIN][INSTEON_ENTITIES]:
                _send_load_aldb_signal(entity_id, reload)
        else:
            _send_load_aldb_signal(entity_id, reload)

    def _send_load_aldb_signal(entity_id, reload):
        """Send the load All-Link database signal to INSTEON entity."""
        signal = f"{entity_id}_{SIGNAL_LOAD_ALDB}"
        dispatcher_send(hass, signal, reload)

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
        print_aldb_to_log(insteon_modem.aldb)

    def x10_all_units_off(service):
        """Send the X10 All Units Off command."""
        housecode = service.data.get(SRV_HOUSECODE)
        insteon_modem.x10_all_units_off(housecode)

    def x10_all_lights_off(service):
        """Send the X10 All Lights Off command."""
        housecode = service.data.get(SRV_HOUSECODE)
        insteon_modem.x10_all_lights_off(housecode)

    def x10_all_lights_on(service):
        """Send the X10 All Lights On command."""
        housecode = service.data.get(SRV_HOUSECODE)
        insteon_modem.x10_all_lights_on(housecode)

    def scene_on(service):
        """Trigger an INSTEON scene ON."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        insteon_modem.trigger_group_on(group)

    def scene_off(service):
        """Trigger an INSTEON scene ON."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        insteon_modem.trigger_group_off(group)

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
        DOMAIN, SRV_X10_ALL_UNITS_OFF, x10_all_units_off, schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SRV_X10_ALL_LIGHTS_OFF, x10_all_lights_off, schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SRV_X10_ALL_LIGHTS_ON, x10_all_lights_on, schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SRV_SCENE_ON, scene_on, schema=TRIGGER_SCENE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_SCENE_OFF, scene_off, schema=TRIGGER_SCENE_SCHEMA
    )
    _LOGGER.debug("Insteon Services registered")


def print_aldb_to_log(aldb):
    """Print the All-Link Database to the log file."""
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
        in_use = "Y" if rec.control_flags.is_in_use else "N"
        mode = "C" if rec.control_flags.is_controller else "R"
        hwm = "Y" if rec.control_flags.is_high_water_mark else "N"
        _LOGGER.info(
            " {:04x}    {:s}     {:s}   {:s}    {:3d} {:s}"
            "   {:3d}   {:3d}   {:3d}".format(
                rec.mem_addr,
                in_use,
                mode,
                hwm,
                rec.group,
                rec.address.human,
                rec.data1,
                rec.data2,
                rec.data3,
            )
        )
