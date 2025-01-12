"""Support for LCN devices."""

from __future__ import annotations

from functools import partial
import logging

import pypck
from pypck.connection import (
    PchkAuthenticationError,
    PchkConnectionFailedError,
    PchkConnectionManager,
    PchkConnectionRefusedError,
    PchkLcnNotConnectedError,
    PchkLicenseError,
)
from pypck.lcn_defs import LcnEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    ADD_ENTITIES_CALLBACKS,
    CONF_ACKNOWLEDGE,
    CONF_DIM_MODE,
    CONF_DOMAIN_DATA,
    CONF_SK_NUM_TRIES,
    CONF_TRANSITION,
    CONNECTION,
    DEVICE_CONNECTIONS,
    DOMAIN,
    PLATFORMS,
)
from .helpers import (
    AddressType,
    InputType,
    async_update_config_entry,
    generate_unique_id,
    register_lcn_address_devices,
    register_lcn_host_device,
)
from .services import register_services
from .websocket import register_panel_and_ws_api

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LCN component."""
    hass.data.setdefault(DOMAIN, {})

    await register_services(hass)
    await register_panel_and_ws_api(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a connection to PCHK host from a config entry."""
    if config_entry.entry_id in hass.data[DOMAIN]:
        return False

    settings = {
        "SK_NUM_TRIES": config_entry.data[CONF_SK_NUM_TRIES],
        "DIM_MODE": pypck.lcn_defs.OutputPortDimMode[config_entry.data[CONF_DIM_MODE]],
        "ACKNOWLEDGE": config_entry.data[CONF_ACKNOWLEDGE],
    }

    # connect to PCHK
    lcn_connection = PchkConnectionManager(
        config_entry.data[CONF_IP_ADDRESS],
        config_entry.data[CONF_PORT],
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_PASSWORD],
        settings=settings,
        connection_id=config_entry.entry_id,
    )

    try:
        # establish connection to PCHK server
        await lcn_connection.async_connect(timeout=15)
    except (
        PchkAuthenticationError,
        PchkLicenseError,
        PchkConnectionRefusedError,
        PchkConnectionFailedError,
        PchkLcnNotConnectedError,
    ) as ex:
        await lcn_connection.async_close()
        raise ConfigEntryNotReady(
            f"Unable to connect to {config_entry.title}: {ex}"
        ) from ex

    _LOGGER.debug('LCN connected to "%s"', config_entry.title)
    hass.data[DOMAIN][config_entry.entry_id] = {
        CONNECTION: lcn_connection,
        DEVICE_CONNECTIONS: {},
        ADD_ENTITIES_CALLBACKS: {},
    }

    # Update config_entry with LCN device serials
    await async_update_config_entry(hass, config_entry)

    # register/update devices for host, modules and groups in device registry
    register_lcn_host_device(hass, config_entry)
    register_lcn_address_devices(hass, config_entry)

    # forward config_entry to components
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # register for LCN bus messages
    device_registry = dr.async_get(hass)
    event_received = partial(async_host_event_received, hass, config_entry)
    input_received = partial(
        async_host_input_received, hass, config_entry, device_registry
    )

    lcn_connection.register_for_events(event_received)
    lcn_connection.register_for_inputs(input_received)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    new_data = {**config_entry.data}

    if config_entry.version == 1:
        # update to 1.2  (add acknowledge flag)
        if config_entry.minor_version < 2:
            new_data[CONF_ACKNOWLEDGE] = False

        # update to 2.1  (fix transitions for lights and switches)
        new_entities_data = [*new_data[CONF_ENTITIES]]
        for entity in new_entities_data:
            if entity[CONF_DOMAIN] in [Platform.LIGHT, Platform.SCENE]:
                if entity[CONF_DOMAIN_DATA][CONF_TRANSITION] is None:
                    entity[CONF_DOMAIN_DATA][CONF_TRANSITION] = 0
                entity[CONF_DOMAIN_DATA][CONF_TRANSITION] /= 1000.0
        new_data[CONF_ENTITIES] = new_entities_data

    hass.config_entries.async_update_entry(
        config_entry, data=new_data, minor_version=1, version=2
    )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Close connection to PCHK host represented by config_entry."""
    # forward unloading to platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok and config_entry.entry_id in hass.data[DOMAIN]:
        host = hass.data[DOMAIN].pop(config_entry.entry_id)
        await host[CONNECTION].async_close()

    return unload_ok


def async_host_event_received(
    hass: HomeAssistant, config_entry: ConfigEntry, event: pypck.lcn_defs.LcnEvent
) -> None:
    """Process received event from LCN."""
    lcn_connection = hass.data[DOMAIN][config_entry.entry_id][CONNECTION]

    async def reload_config_entry() -> None:
        """Close connection and schedule config entry for reload."""
        await lcn_connection.async_close()
        hass.config_entries.async_schedule_reload(config_entry.entry_id)

    if event in (
        LcnEvent.CONNECTION_LOST,
        LcnEvent.PING_TIMEOUT,
    ):
        _LOGGER.info('The connection to host "%s" has been lost', config_entry.title)
        hass.async_create_task(reload_config_entry())
    elif event == LcnEvent.BUS_DISCONNECTED:
        _LOGGER.info(
            'The connection to the LCN bus via host "%s" has been disconnected',
            config_entry.title,
        )
        hass.async_create_task(reload_config_entry())


def async_host_input_received(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    inp: pypck.inputs.Input,
) -> None:
    """Process received input object (command) from LCN bus."""
    if not isinstance(inp, pypck.inputs.ModInput):
        return

    lcn_connection = hass.data[DOMAIN][config_entry.entry_id][CONNECTION]
    logical_address = lcn_connection.physical_to_logical(inp.physical_source_addr)
    address = (
        logical_address.seg_id,
        logical_address.addr_id,
        logical_address.is_group,
    )
    identifiers = {(DOMAIN, generate_unique_id(config_entry.entry_id, address))}
    device = device_registry.async_get_device(identifiers=identifiers)

    if isinstance(inp, pypck.inputs.ModStatusAccessControl):
        _async_fire_access_control_event(hass, device, address, inp)
    elif isinstance(inp, pypck.inputs.ModSendKeysHost):
        _async_fire_send_keys_event(hass, device, address, inp)


def _async_fire_access_control_event(
    hass: HomeAssistant,
    device: dr.DeviceEntry | None,
    address: AddressType,
    inp: InputType,
) -> None:
    """Fire access control event (transponder, transmitter, fingerprint, codelock)."""
    event_data = {
        "segment_id": address[0],
        "module_id": address[1],
        "code": inp.code,
    }

    if device is not None:
        event_data.update({CONF_DEVICE_ID: device.id})

    if inp.periphery == pypck.lcn_defs.AccessControlPeriphery.TRANSMITTER:
        event_data.update(
            {"level": inp.level, "key": inp.key, "action": inp.action.value}
        )

    event_name = f"lcn_{inp.periphery.value.lower()}"
    hass.bus.async_fire(event_name, event_data)


def _async_fire_send_keys_event(
    hass: HomeAssistant,
    device: dr.DeviceEntry | None,
    address: AddressType,
    inp: InputType,
) -> None:
    """Fire send_keys event."""
    for table, action in enumerate(inp.actions):
        if action == pypck.lcn_defs.SendKeyCommand.DONTSEND:
            continue

        for key, selected in enumerate(inp.keys):
            if not selected:
                continue
            event_data = {
                "segment_id": address[0],
                "module_id": address[1],
                "key": pypck.lcn_defs.Key(table * 8 + key).name.lower(),
                "action": action.name.lower(),
            }

            if device is not None:
                event_data.update({CONF_DEVICE_ID: device.id})

            hass.bus.async_fire("lcn_send_keys", event_data)
