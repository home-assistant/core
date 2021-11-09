"""Support for INSTEON Modems (PLM and Hub)."""
import asyncio
from contextlib import suppress
import logging

from pyinsteon import async_close, async_connect, devices

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PLATFORM, EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryNotReady

from . import api
from .const import (
    CONF_CAT,
    CONF_DIM_STEPS,
    CONF_HOUSECODE,
    CONF_OVERRIDE,
    CONF_SUBCAT,
    CONF_UNITCODE,
    CONF_X10,
    DOMAIN,
    INSTEON_PLATFORMS,
    ON_OFF_EVENTS,
)
from .schemas import convert_yaml_to_config_flow
from .utils import (
    add_on_off_event_device,
    async_register_services,
    get_device_platforms,
    register_new_device_callback,
)

_LOGGER = logging.getLogger(__name__)
OPTIONS = "options"


async def async_get_device_config(hass, config_entry):
    """Initiate the connection and services."""
    # Make a copy of addresses due to edge case where the list of devices could change during status update
    # Cannot be done concurrently due to issues with the underlying protocol.
    for address in list(devices):
        with suppress(AttributeError):
            await devices[address].async_status()

    await devices.async_load(id_devices=1)
    for addr in devices:
        device = devices[addr]
        flags = True
        for name in device.operating_flags:
            if not device.operating_flags[name].is_loaded:
                flags = False
                break
        if flags:
            for name in device.properties:
                if not device.properties[name].is_loaded:
                    flags = False
                    break

        # Cannot be done concurrently due to issues with the underlying protocol.
        if not device.aldb.is_loaded or not flags:
            await device.async_read_config()

    await devices.async_save(workdir=hass.config.config_dir)


async def close_insteon_connection(*args):
    """Close the Insteon connection."""
    await async_close()


async def async_setup(hass, config):
    """Set up the Insteon platform."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    data, options = convert_yaml_to_config_flow(conf)
    if options:
        hass.data[DOMAIN] = {}
        hass.data[DOMAIN][OPTIONS] = options
    # Create a config entry with the connection data
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=data
        )
    )
    return True


async def async_setup_entry(hass, entry):
    """Set up an Insteon entry."""

    if not devices.modem:
        try:
            await async_connect(**entry.data)
        except ConnectionError as exception:
            _LOGGER.error("Could not connect to Insteon modem")
            raise ConfigEntryNotReady from exception

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_insteon_connection)
    )

    await devices.async_load(
        workdir=hass.config.config_dir, id_devices=0, load_modem_aldb=0
    )

    # If options existed in YAML and have not already been saved to the config entry
    # add them now
    if (
        not entry.options
        and entry.source == SOURCE_IMPORT
        and hass.data.get(DOMAIN)
        and hass.data[DOMAIN].get(OPTIONS)
    ):
        hass.config_entries.async_update_entry(
            entry=entry,
            options=hass.data[DOMAIN][OPTIONS],
        )

    for device_override in entry.options.get(CONF_OVERRIDE, []):
        # Override the device default capabilities for a specific address
        address = device_override.get("address")
        if not devices.get(address):
            cat = device_override[CONF_CAT]
            subcat = device_override[CONF_SUBCAT]
            devices.set_id(address, cat, subcat, 0)

    for device in entry.options.get(CONF_X10, []):
        housecode = device.get(CONF_HOUSECODE)
        unitcode = device.get(CONF_UNITCODE)
        x10_type = "on_off"
        steps = device.get(CONF_DIM_STEPS, 22)
        if device.get(CONF_PLATFORM) == "light":
            x10_type = "dimmable"
        elif device.get(CONF_PLATFORM) == "binary_sensor":
            x10_type = "sensor"
        _LOGGER.debug(
            "Adding X10 device to Insteon: %s %d %s", housecode, unitcode, x10_type
        )
        device = devices.add_x10_device(housecode, unitcode, x10_type, steps)

    for platform in INSTEON_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    for address in devices:
        device = devices[address]
        platforms = get_device_platforms(device)
        if ON_OFF_EVENTS in platforms:
            add_on_off_event_device(hass, device)

    _LOGGER.debug("Insteon device count: %s", len(devices))
    register_new_device_callback(hass)
    async_register_services(hass)

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(devices.modem.address))},
        manufacturer="Smart Home",
        name=f"{devices.modem.description} {devices.modem.address}",
        model=f"{devices.modem.model} ({devices.modem.cat!r}, 0x{devices.modem.subcat:02x})",
        sw_version=f"{devices.modem.firmware:02x} Engine Version: {devices.modem.engine_version}",
    )

    api.async_load_api(hass)

    asyncio.create_task(async_get_device_config(hass, entry))

    return True
