"""Utilities used by insteon component."""

import logging

from pyinsteon import devices
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

from homeassistant.const import CONF_ENTITY_ID, ENTITY_MATCH_ALL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.service import async_register_admin_service

from .const import (
    DOMAIN,
    SIGNAL_ADD_DEFAULT_LINKS,
    SIGNAL_LOAD_ALDB,
    SIGNAL_PRINT_ALDB,
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
from .schemas import (
    ADD_ALL_LINK_SCHEMA,
    ADD_DEFAULT_LINKS_SCHEMA,
    DEL_ALL_LINK_SCHEMA,
    LOAD_ALDB_SCHEMA,
    PRINT_ALDB_SCHEMA,
    TRIGGER_SCENE_SCHEMA,
    X10_HOUSECODE_SCHEMA,
)
from .utils import async_save_devices, print_aldb_to_log

_LOGGER = logging.getLogger(__name__)


async def _async_srv_add_all_link(service: ServiceCall) -> None:
    """Add an INSTEON All-Link between two devices."""
    group = service.data[SRV_ALL_LINK_GROUP]
    mode = service.data[SRV_ALL_LINK_MODE]
    link_mode = mode.lower() == SRV_CONTROLLER
    await async_enter_linking_mode(link_mode, group)


async def _async_srv_del_all_link(service: ServiceCall) -> None:
    """Delete an INSTEON All-Link between two devices."""
    group = service.data.get(SRV_ALL_LINK_GROUP)
    await async_enter_unlinking_mode(group)


async def _async_srv_load_aldb(service: ServiceCall) -> None:
    """Load the device All-Link database."""
    entity_id = service.data[CONF_ENTITY_ID]
    reload = service.data[SRV_LOAD_DB_RELOAD]
    if entity_id.lower() == ENTITY_MATCH_ALL:
        await _async_srv_load_aldb_all(service.hass, reload)
    else:
        signal = f"{entity_id}_{SIGNAL_LOAD_ALDB}"
        async_dispatcher_send(service.hass, signal, reload)


async def _async_srv_load_aldb_all(hass: HomeAssistant, reload: bool) -> None:
    """Load the All-Link database for all devices."""
    # Cannot be done concurrently due to issues with the underlying protocol.
    for address in devices:
        device = devices[address]
        if device != devices.modem and device.cat != 0x03:
            await device.aldb.async_load(refresh=reload)
            await async_save_devices(hass)


def _print_aldb(service: ServiceCall) -> None:
    """Print the All-Link Database for a device."""
    # For now this sends logs to the log file.
    # Future direction is to create an INSTEON control panel.
    entity_id = service.data[CONF_ENTITY_ID]
    signal = f"{entity_id}_{SIGNAL_PRINT_ALDB}"
    dispatcher_send(service.hass, signal)


def _print_im_aldb(service: ServiceCall) -> None:
    """Print the All-Link Database for a device."""
    # For now this sends logs to the log file.
    # Future direction is to create an INSTEON control panel.
    print_aldb_to_log(devices.modem.aldb)


async def _async_srv_x10_all_units_off(service: ServiceCall) -> None:
    """Send the X10 All Units Off command."""
    housecode = service.data.get(SRV_HOUSECODE)
    await async_x10_all_units_off(housecode)


async def _async_srv_x10_all_lights_off(service: ServiceCall) -> None:
    """Send the X10 All Lights Off command."""
    housecode = service.data.get(SRV_HOUSECODE)
    await async_x10_all_lights_off(housecode)


async def _async_srv_x10_all_lights_on(service: ServiceCall) -> None:
    """Send the X10 All Lights On command."""
    housecode = service.data.get(SRV_HOUSECODE)
    await async_x10_all_lights_on(housecode)


async def _async_srv_scene_on(service: ServiceCall) -> None:
    """Trigger an INSTEON scene ON."""
    group = service.data.get(SRV_ALL_LINK_GROUP)
    await async_trigger_scene_on(group)


async def _async_srv_scene_off(service: ServiceCall) -> None:
    """Trigger an INSTEON scene ON."""
    group = service.data.get(SRV_ALL_LINK_GROUP)
    await async_trigger_scene_off(group)


@callback
def _async_add_default_links(service: ServiceCall) -> None:
    """Add the default All-Link entries to a device."""
    entity_id = service.data[CONF_ENTITY_ID]
    signal = f"{entity_id}_{SIGNAL_ADD_DEFAULT_LINKS}"
    async_dispatcher_send(service.hass, signal)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services used by insteon component."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SRV_ADD_ALL_LINK,
        _async_srv_add_all_link,
        schema=ADD_ALL_LINK_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SRV_DEL_ALL_LINK,
        _async_srv_del_all_link,
        schema=DEL_ALL_LINK_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SRV_LOAD_ALDB, _async_srv_load_aldb, schema=LOAD_ALDB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_PRINT_ALDB, _print_aldb, schema=PRINT_ALDB_SCHEMA
    )
    hass.services.async_register(DOMAIN, SRV_PRINT_IM_ALDB, _print_im_aldb, schema=None)
    hass.services.async_register(
        DOMAIN,
        SRV_X10_ALL_UNITS_OFF,
        _async_srv_x10_all_units_off,
        schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SRV_X10_ALL_LIGHTS_OFF,
        _async_srv_x10_all_lights_off,
        schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SRV_X10_ALL_LIGHTS_ON,
        _async_srv_x10_all_lights_on,
        schema=X10_HOUSECODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SRV_SCENE_ON, _async_srv_scene_on, schema=TRIGGER_SCENE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SRV_SCENE_OFF, _async_srv_scene_off, schema=TRIGGER_SCENE_SCHEMA
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SRV_ADD_DEFAULT_LINKS,
        _async_add_default_links,
        schema=ADD_DEFAULT_LINKS_SCHEMA,
    )
    _LOGGER.debug("Insteon Services registered")
