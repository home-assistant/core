"""Support for devices connected to UniFi POE."""
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .config_flow import get_controller_id_from_config_entry
from .const import (
    ATTR_MANUFACTURER,
    DOMAIN as UNIFI_DOMAIN,
    LOGGER,
    UNIFI_WIRELESS_CLIENTS,
)
from .controller import UniFiController

SAVE_DELAY = 10
STORAGE_KEY = "unifi_data"
STORAGE_VERSION = 1


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    hass.data[UNIFI_WIRELESS_CLIENTS] = wireless_clients = UnifiWirelessClients(hass)
    await wireless_clients.async_load()

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the UniFi component."""
    hass.data.setdefault(UNIFI_DOMAIN, {})

    controller = UniFiController(hass, config_entry)
    if not await controller.async_setup():
        return False

    hass.data[UNIFI_DOMAIN][config_entry.entry_id] = controller

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, controller.shutdown)

    LOGGER.debug("UniFi config options %s", config_entry.options)

    if controller.mac is None:
        return True

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, controller.mac)},
        default_manufacturer=ATTR_MANUFACTURER,
        default_model="UniFi Controller",
        default_name="UniFi Controller",
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    controller = hass.data[UNIFI_DOMAIN].pop(config_entry.entry_id)
    return await controller.async_reset()


class UnifiWirelessClients:
    """Class to store clients known to be wireless.

    This is needed since wireless devices going offline might get marked as wired by UniFi.
    """

    def __init__(self, hass):
        """Set up client storage."""
        self.hass = hass
        self.data = {}
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self):
        """Load data from file."""
        data = await self._store.async_load()

        if data is not None:
            self.data = data

    @callback
    def get_data(self, config_entry):
        """Get data related to a specific controller."""
        controller_id = get_controller_id_from_config_entry(config_entry)
        key = config_entry.entry_id
        if controller_id in self.data:
            key = controller_id

        data = self.data.get(key, {"wireless_devices": []})
        return set(data["wireless_devices"])

    @callback
    def update_data(self, data, config_entry):
        """Update data and schedule to save to file."""
        controller_id = get_controller_id_from_config_entry(config_entry)
        if controller_id in self.data:
            self.data.pop(controller_id)

        self.data[config_entry.entry_id] = {"wireless_devices": list(data)}
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self):
        """Return data of UniFi wireless clients to store in a file."""
        return self.data
