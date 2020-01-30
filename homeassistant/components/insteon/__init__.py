"""Support for INSTEON Modems (PLM and Hub)."""
import logging

import insteonplm

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
    CONF_X10_ALL_LIGHTS_OFF,
    CONF_X10_ALL_LIGHTS_ON,
    CONF_X10_ALL_UNITS_OFF,
    DOMAIN,
    INSTEON_ENTITIES,
)
from .schemas import CONFIG_SCHEMA  # noqa F440
from .utils import async_register_services, register_new_device_callback

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the connection to the modem."""
    insteon_modem = None

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    host = conf.get(CONF_HOST)
    ip_port = conf.get(CONF_IP_PORT)
    username = conf.get(CONF_HUB_USERNAME)
    password = conf.get(CONF_HUB_PASSWORD)
    hub_version = conf.get(CONF_HUB_VERSION)
    overrides = conf.get(CONF_OVERRIDE, [])
    x10_devices = conf.get(CONF_X10, [])
    x10_all_units_off_housecode = conf.get(CONF_X10_ALL_UNITS_OFF)
    x10_all_lights_on_housecode = conf.get(CONF_X10_ALL_LIGHTS_ON)
    x10_all_lights_off_housecode = conf.get(CONF_X10_ALL_LIGHTS_OFF)

    if host:
        _LOGGER.info("Connecting to Insteon Hub on %s", host)
        conn = await insteonplm.Connection.create(
            host=host,
            port=ip_port,
            username=username,
            password=password,
            hub_version=hub_version,
            loop=hass.loop,
            workdir=hass.config.config_dir,
        )
    else:
        _LOGGER.info("Looking for Insteon PLM on %s", port)
        conn = await insteonplm.Connection.create(
            device=port, loop=hass.loop, workdir=hass.config.config_dir
        )

    insteon_modem = conn.protocol

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["modem"] = insteon_modem
    hass.data[DOMAIN][INSTEON_ENTITIES] = set()

    register_new_device_callback(hass, config, insteon_modem)
    async_register_services(hass, config, insteon_modem)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, conn.close)

    for device_override in overrides:
        #
        # Override the device default capabilities for a specific address
        #
        address = device_override.get("address")
        for prop in device_override:
            if prop in [CONF_CAT, CONF_SUBCAT]:
                insteon_modem.devices.add_override(address, prop, device_override[prop])
            elif prop in [CONF_FIRMWARE, CONF_PRODUCT_KEY]:
                insteon_modem.devices.add_override(
                    address, CONF_PRODUCT_KEY, device_override[prop]
                )

    if x10_all_units_off_housecode:
        device = insteon_modem.add_x10_device(
            x10_all_units_off_housecode, 20, "allunitsoff"
        )
    if x10_all_lights_on_housecode:
        device = insteon_modem.add_x10_device(
            x10_all_lights_on_housecode, 21, "alllightson"
        )
    if x10_all_lights_off_housecode:
        device = insteon_modem.add_x10_device(
            x10_all_lights_off_housecode, 22, "alllightsoff"
        )
    for device in x10_devices:
        housecode = device.get(CONF_HOUSECODE)
        unitcode = device.get(CONF_UNITCODE)
        x10_type = "onoff"
        steps = device.get(CONF_DIM_STEPS, 22)
        if device.get(CONF_PLATFORM) == "light":
            x10_type = "dimmable"
        elif device.get(CONF_PLATFORM) == "binary_sensor":
            x10_type = "sensor"
        _LOGGER.debug(
            "Adding X10 device to Insteon: %s %d %s", housecode, unitcode, x10_type
        )
        device = insteon_modem.add_x10_device(housecode, unitcode, x10_type)
        if device and hasattr(device.states[0x01], "steps"):
            device.states[0x01].steps = steps

    return True
