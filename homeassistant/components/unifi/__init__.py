"""Support for devices connected to UniFi POE."""
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import CONF_CONTROLLER, CONF_SITE_ID, CONTROLLER_ID, DOMAIN
from .controller import UniFiController


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
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
