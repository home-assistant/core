"""Support for INSTEON Modems (PLM and Hub)."""
import asyncio
import logging

from pyinsteon import async_close, async_connect, devices

from homeassistant.const import (
    CONF_HOST,
    CONF_PLATFORM,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)

from .const import (
    CONF_CAT,
    CONF_DIM_STEPS,
    CONF_FIRMWARE,
    CONF_HOUSECODE,
    CONF_HUB_PASSWORD,
    CONF_HUB_USERNAME,
    CONF_HUB_VERSION,
    CONF_IP_PORT,
    CONF_OVERRIDE,
    CONF_PRODUCT_KEY,
    CONF_SUBCAT,
    CONF_UNITCODE,
    CONF_X10,
    DOMAIN,
    INSTEON_COMPONENTS,
    ON_OFF_EVENTS,
)
from .schemas import CONFIG_SCHEMA  # noqa F440
from .utils import (
    add_on_off_event_device,
    async_register_services,
    get_device_platforms,
    register_new_device_callback,
)

_LOGGER = logging.getLogger(__name__)


async def async_id_unknown_devices(config_dir):
    """Send device ID commands to all unidentified devices."""
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

    await devices.async_save(workdir=config_dir)


async def async_setup_platforms(hass, config):
    """Initiate the connection and services."""
    tasks = [
        hass.helpers.discovery.async_load_platform(component, DOMAIN, {}, config)
        for component in INSTEON_COMPONENTS
    ]
    await asyncio.gather(*tasks)

    for address in devices:
        device = devices[address]
        platforms = get_device_platforms(device)
        if ON_OFF_EVENTS in platforms:
            add_on_off_event_device(hass, device)

    _LOGGER.debug("Insteon device count: %s", len(devices))
    register_new_device_callback(hass, config)
    async_register_services(hass)

    # Cannot be done concurrently due to issues with the underlying protocol.
    for address in devices:
        await devices[address].async_status()
    await async_id_unknown_devices(hass.config.config_dir)


async def close_insteon_connection(*args):
    """Close the Insteon connection."""
    await async_close()


async def async_setup(hass, config):
    """Set up the connection to the modem."""

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    host = conf.get(CONF_HOST)
    ip_port = conf.get(CONF_IP_PORT)
    username = conf.get(CONF_HUB_USERNAME)
    password = conf.get(CONF_HUB_PASSWORD)
    hub_version = conf.get(CONF_HUB_VERSION)

    if host:
        _LOGGER.info("Connecting to Insteon Hub on %s:%d", host, ip_port)
    else:
        _LOGGER.info("Connecting to Insteon PLM on %s", port)

    try:
        await async_connect(
            device=port,
            host=host,
            port=ip_port,
            username=username,
            password=password,
            hub_version=hub_version,
        )
    except ConnectionError:
        _LOGGER.error("Could not connect to Insteon modem")
        return False
    _LOGGER.info("Connection to Insteon modem successful")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_insteon_connection)
    conf = config[DOMAIN]
    overrides = conf.get(CONF_OVERRIDE, [])
    x10_devices = conf.get(CONF_X10, [])

    await devices.async_load(
        workdir=hass.config.config_dir, id_devices=0, load_modem_aldb=0
    )

    for device_override in overrides:
        # Override the device default capabilities for a specific address
        address = device_override.get("address")
        if not devices.get(address):
            cat = device_override[CONF_CAT]
            subcat = device_override[CONF_SUBCAT]
            firmware = device_override.get(CONF_FIRMWARE)
            if firmware is None:
                firmware = device_override.get(CONF_PRODUCT_KEY, 0)
            devices.set_id(address, cat, subcat, firmware)

    for device in x10_devices:
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

    asyncio.create_task(async_setup_platforms(hass, config))
    return True
