"""Support for devices connected to UniFi POE."""
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import (
    CONF_CONTROLLER, CONF_SITE_ID, CONTROLLER_ID, DOMAIN, UNIFI_CONFIG)
from .controller import UniFiController
from .device_tracker import (
    CONF_DT_SITE_ID, PLATFORM_SCHEMA as DEVICE_TRACKER_SCHEMA)


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    unifi_config = []

    if 'device_tracker' in config:
        for dt_conf in config['device_tracker']:
            if dt_conf['platform'] == DOMAIN:
                unifi_config.append(DEVICE_TRACKER_SCHEMA(dt_conf))

    hass.data[UNIFI_CONFIG] = unifi_config

    for unifi in unifi_config:
        exist = False

        for entry in hass.config_entries.async_entries(DOMAIN):
            if unifi[CONF_HOST] == entry.data[CONF_CONTROLLER][CONF_HOST] and \
                    unifi[CONF_DT_SITE_ID] == \
                        entry.data[CONF_CONTROLLER][CONF_SITE_ID]:
                exist = True
                break

        if not exist:
            hass.async_create_task(hass.config_entries.flow.async_init(
                DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
                data=unifi
            ))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the UniFi component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    controller = UniFiController(hass, config_entry)

    controller_id = CONTROLLER_ID.format(
        host=config_entry.data[CONF_CONTROLLER][CONF_HOST],
        site=config_entry.data[CONF_CONTROLLER][CONF_SITE_ID]
    )

    hass.data[DOMAIN][controller_id] = controller

    if not await controller.async_setup():
        return False

    if controller.mac is None:
        return True

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, controller.mac)},
        manufacturer='Ubiquiti',
        model="UniFi Controller",
        name="UniFi Controller",
        # sw_version=config.raw['swversion'],
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    controller_id = CONTROLLER_ID.format(
        host=config_entry.data[CONF_CONTROLLER][CONF_HOST],
        site=config_entry.data[CONF_CONTROLLER][CONF_SITE_ID]
    )
    controller = hass.data[DOMAIN].pop(controller_id)
    return await controller.async_reset()
