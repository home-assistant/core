"""Support for Zigbee Home Automation devices."""

import asyncio
import logging

import voluptuous as vol

from homeassistant import config_entries, const as ha_const
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import HomeAssistantType

from . import api
from .core import ZHAGateway
from .core.const import (
    COMPONENTS,
    CONF_BAUDRATE,
    CONF_DATABASE,
    CONF_DEVICE_CONFIG,
    CONF_ENABLE_QUIRKS,
    CONF_RADIO_TYPE,
    CONF_USB_PATH,
    DATA_ZHA,
    DATA_ZHA_CONFIG,
    DATA_ZHA_DISPATCHERS,
    DATA_ZHA_GATEWAY,
    DATA_ZHA_PLATFORM_LOADED,
    DEFAULT_BAUDRATE,
    DEFAULT_RADIO_TYPE,
    DOMAIN,
    SIGNAL_ADD_ENTITIES,
    RadioType,
)

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({vol.Optional(ha_const.CONF_TYPE): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_RADIO_TYPE, default=DEFAULT_RADIO_TYPE): cv.enum(
                    RadioType
                ),
                CONF_USB_PATH: cv.string,
                vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
                vol.Optional(CONF_DATABASE): cv.string,
                vol.Optional(CONF_DEVICE_CONFIG, default={}): vol.Schema(
                    {cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}
                ),
                vol.Optional(CONF_ENABLE_QUIRKS, default=True): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Zigbee definitions
CENTICELSIUS = "C-100"

# Internal definitions
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up ZHA from config."""
    hass.data[DATA_ZHA] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    hass.data[DATA_ZHA][DATA_ZHA_CONFIG] = conf

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_USB_PATH: conf[CONF_USB_PATH],
                    CONF_RADIO_TYPE: conf.get(CONF_RADIO_TYPE).value,
                },
            )
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up ZHA.

    Will automatically load components to support devices found on the network.
    """

    zha_data = hass.data.setdefault(DATA_ZHA, {})
    config = zha_data.get(DATA_ZHA_CONFIG, {})

    for component in COMPONENTS:
        zha_data.setdefault(component, [])

    if config.get(CONF_ENABLE_QUIRKS, True):
        # needs to be done here so that the ZHA module is finished loading
        # before zhaquirks is imported
        import zhaquirks  # noqa: F401 pylint: disable=unused-import, import-outside-toplevel, import-error

    zha_gateway = ZHAGateway(hass, config, config_entry)
    await zha_gateway.async_initialize()

    zha_data[DATA_ZHA_DISPATCHERS] = []
    zha_data[DATA_ZHA_PLATFORM_LOADED] = []
    for component in COMPONENTS:
        coro = hass.config_entries.async_forward_entry_setup(config_entry, component)
        zha_data[DATA_ZHA_PLATFORM_LOADED].append(hass.async_create_task(coro))

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_ZIGBEE, str(zha_gateway.application_controller.ieee))},
        identifiers={(DOMAIN, str(zha_gateway.application_controller.ieee))},
        name="Zigbee Coordinator",
        manufacturer="ZHA",
        model=zha_gateway.radio_description,
    )

    api.async_load_api(hass)

    async def async_zha_shutdown(event):
        """Handle shutdown tasks."""
        await zha_data[DATA_ZHA_GATEWAY].shutdown()
        await zha_data[DATA_ZHA_GATEWAY].async_update_device_storage()

    hass.bus.async_listen_once(ha_const.EVENT_HOMEASSISTANT_STOP, async_zha_shutdown)
    asyncio.create_task(async_load_entities(hass, config_entry))
    return True


async def async_unload_entry(hass, config_entry):
    """Unload ZHA config entry."""
    await hass.data[DATA_ZHA][DATA_ZHA_GATEWAY].shutdown()

    api.async_unload_api(hass)

    dispatchers = hass.data[DATA_ZHA].get(DATA_ZHA_DISPATCHERS, [])
    for unsub_dispatcher in dispatchers:
        unsub_dispatcher()

    for component in COMPONENTS:
        await hass.config_entries.async_forward_entry_unload(config_entry, component)

    return True


async def async_load_entities(
    hass: HomeAssistantType, config_entry: config_entries.ConfigEntry
) -> None:
    """Load entities after integration was setup."""
    await hass.data[DATA_ZHA][DATA_ZHA_GATEWAY].async_prepare_entities()
    to_setup = hass.data[DATA_ZHA][DATA_ZHA_PLATFORM_LOADED]
    results = await asyncio.gather(*to_setup, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            _LOGGER.warning("Couldn't setup zha platform: %s", res)
    async_dispatcher_send(hass, SIGNAL_ADD_ENTITIES)
