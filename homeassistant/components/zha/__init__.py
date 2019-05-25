"""Support for Zigbee Home Automation devices."""
import logging

import voluptuous as vol

from homeassistant import config_entries, const as ha_const
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE

# Loading the config flow file will register the flow
from . import config_flow  # noqa  # pylint: disable=unused-import
from . import api
from .core import ZHAGateway
from .core.channels.registry import populate_channel_registry
from .core.const import (
    COMPONENTS, CONF_BAUDRATE, CONF_DATABASE, CONF_DEVICE_CONFIG,
    CONF_RADIO_TYPE, CONF_USB_PATH, DATA_ZHA, DATA_ZHA_CONFIG,
    DATA_ZHA_CORE_COMPONENT, DATA_ZHA_DISPATCHERS, DATA_ZHA_GATEWAY,
    DEFAULT_BAUDRATE, DEFAULT_RADIO_TYPE, DOMAIN, ENABLE_QUIRKS, RadioType)
from .core.registries import establish_device_mappings

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(ha_const.CONF_TYPE): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(
            CONF_RADIO_TYPE,
            default=DEFAULT_RADIO_TYPE
        ): cv.enum(RadioType),
        CONF_USB_PATH: cv.string,
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
        vol.Optional(CONF_DATABASE): cv.string,
        vol.Optional(CONF_DEVICE_CONFIG, default={}):
            vol.Schema({cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}),
        vol.Optional(ENABLE_QUIRKS, default=True): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

# Zigbee definitions
CENTICELSIUS = 'C-100'

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
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': config_entries.SOURCE_IMPORT},
            data={
                CONF_USB_PATH: conf[CONF_USB_PATH],
                CONF_RADIO_TYPE: conf.get(CONF_RADIO_TYPE).value
            }
        ))
    return True


async def async_setup_entry(hass, config_entry):
    """Set up ZHA.

    Will automatically load components to support devices found on the network.
    """
    establish_device_mappings()
    populate_channel_registry()

    for component in COMPONENTS:
        hass.data[DATA_ZHA][component] = (
            hass.data[DATA_ZHA].get(component, {})
        )

    hass.data[DATA_ZHA] = hass.data.get(DATA_ZHA, {})
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS] = []
    config = hass.data[DATA_ZHA].get(DATA_ZHA_CONFIG, {})

    if config.get(ENABLE_QUIRKS, True):
        # needs to be done here so that the ZHA module is finished loading
        # before zhaquirks is imported
        # pylint: disable=W0611, W0612
        import zhaquirks  # noqa

    zha_gateway = ZHAGateway(hass, config)
    await zha_gateway.async_initialize(config_entry)

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={
            (
                CONNECTION_ZIGBEE,
                str(zha_gateway.application_controller.ieee)
            )
        },
        identifiers={
            (
                DOMAIN,
                str(zha_gateway.application_controller.ieee)
            )
        },
        name="Zigbee Coordinator",
        manufacturer="ZHA",
        model=zha_gateway.radio_description,
    )

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                config_entry, component)
        )

    api.async_load_api(hass)

    async def async_zha_shutdown(event):
        """Handle shutdown tasks."""
        await hass.data[DATA_ZHA][DATA_ZHA_GATEWAY].shutdown()
        await hass.data[DATA_ZHA][
            DATA_ZHA_GATEWAY].async_update_device_storage()

    hass.bus.async_listen_once(
        ha_const.EVENT_HOMEASSISTANT_STOP, async_zha_shutdown)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload ZHA config entry."""
    await hass.data[DATA_ZHA][DATA_ZHA_GATEWAY].shutdown()

    api.async_unload_api(hass)

    dispatchers = hass.data[DATA_ZHA].get(DATA_ZHA_DISPATCHERS, [])
    for unsub_dispatcher in dispatchers:
        unsub_dispatcher()

    for component in COMPONENTS:
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    # clean up device entities
    component = hass.data[DATA_ZHA][DATA_ZHA_CORE_COMPONENT]
    entity_ids = [entity.entity_id for entity in component.entities]
    for entity_id in entity_ids:
        await component.async_remove_entity(entity_id)

    del hass.data[DATA_ZHA]
    return True
