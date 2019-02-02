"""
Support for Zigbee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging
import os
import types

import voluptuous as vol

from homeassistant import config_entries, const as ha_const
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE

# Loading the config flow file will register the flow
from . import config_flow  # noqa  # pylint: disable=unused-import
from . import api
from .core.gateway import ZHAGateway
from .const import (
    COMPONENTS, CONF_BAUDRATE, CONF_DATABASE, CONF_DEVICE_CONFIG,
    CONF_RADIO_TYPE, CONF_USB_PATH, DATA_ZHA, DATA_ZHA_BRIDGE_ID,
    DATA_ZHA_CONFIG, DATA_ZHA_CORE_COMPONENT, DATA_ZHA_DISPATCHERS,
    DATA_ZHA_RADIO, DEFAULT_BAUDRATE, DEFAULT_DATABASE_NAME,
    DEFAULT_RADIO_TYPE, DOMAIN, RadioType, DATA_ZHA_CORE_EVENTS,
    ENABLE_QUIRKS)

REQUIREMENTS = [
    'bellows==0.7.0',
    'zigpy==0.2.0',
    'zigpy-xbee==0.1.1',
    'zha-quirks==0.0.6',
    'zigpy-deconz==0.0.1'
]

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
    hass.data[DATA_ZHA] = hass.data.get(DATA_ZHA, {})
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS] = []

    config = hass.data[DATA_ZHA].get(DATA_ZHA_CONFIG, {})

    if config.get(ENABLE_QUIRKS, True):
        # needs to be done here so that the ZHA module is finished loading
        # before zhaquirks is imported
        # pylint: disable=W0611, W0612
        import zhaquirks  # noqa

    usb_path = config_entry.data.get(CONF_USB_PATH)
    baudrate = config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
    radio_type = config_entry.data.get(CONF_RADIO_TYPE)
    if radio_type == RadioType.ezsp.name:
        import bellows.ezsp
        from bellows.zigbee.application import ControllerApplication
        radio = bellows.ezsp.EZSP()
        radio_description = "EZSP"
    elif radio_type == RadioType.xbee.name:
        import zigpy_xbee.api
        from zigpy_xbee.zigbee.application import ControllerApplication
        radio = zigpy_xbee.api.XBee()
        radio_description = "XBee"
    elif radio_type == RadioType.deconz.name:
        import zigpy_deconz.api
        from zigpy_deconz.zigbee.application import ControllerApplication
        radio = zigpy_deconz.api.Deconz()
        radio_description = "Deconz"

    await radio.connect(usb_path, baudrate)
    hass.data[DATA_ZHA][DATA_ZHA_RADIO] = radio

    if CONF_DATABASE in config:
        database = config[CONF_DATABASE]
    else:
        database = os.path.join(hass.config.config_dir, DEFAULT_DATABASE_NAME)

    # patch zigpy listener to prevent flooding logs with warnings due to
    # how zigpy implemented its listeners
    from zigpy.appdb import ClusterPersistingListener

    def zha_send_event(self, cluster, command, args):
        pass

    ClusterPersistingListener.zha_send_event = types.MethodType(
        zha_send_event,
        ClusterPersistingListener
    )

    application_controller = ControllerApplication(radio, database)
    zha_gateway = ZHAGateway(hass, config)
    application_controller.add_listener(zha_gateway)
    await application_controller.startup(auto_form=True)

    for device in application_controller.devices.values():
        hass.async_create_task(
            zha_gateway.async_device_initialized(device, False))

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_ZIGBEE, str(application_controller.ieee))},
        identifiers={(DOMAIN, str(application_controller.ieee))},
        name="Zigbee Coordinator",
        manufacturer="ZHA",
        model=radio_description,
    )

    hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID] = str(application_controller.ieee)

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                config_entry, component)
        )

    api.async_load_api(hass, application_controller, zha_gateway)

    def zha_shutdown(event):
        """Close radio."""
        hass.data[DATA_ZHA][DATA_ZHA_RADIO].close()

    hass.bus.async_listen_once(ha_const.EVENT_HOMEASSISTANT_STOP, zha_shutdown)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload ZHA config entry."""
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

    # clean up events
    hass.data[DATA_ZHA][DATA_ZHA_CORE_EVENTS].clear()

    _LOGGER.debug("Closing zha radio")
    hass.data[DATA_ZHA][DATA_ZHA_RADIO].close()

    del hass.data[DATA_ZHA]
    return True
