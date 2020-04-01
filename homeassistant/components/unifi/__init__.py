"""Support for devices connected to UniFi POE."""
import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .config_flow import get_controller_id_from_config_entry
from .const import ATTR_MANUFACTURER, DOMAIN, UNIFI_WIRELESS_CLIENTS
from .controller import UniFiController

SAVE_DELAY = 10
STORAGE_KEY = "unifi_data"
STORAGE_VERSION = 1

CONFIG_SCHEMA = vol.Schema(
    cv.deprecated(DOMAIN, invalidation_version="0.109"), {DOMAIN: cv.match_all}
)


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    hass.data[UNIFI_WIRELESS_CLIENTS] = wireless_clients = UnifiWirelessClients(hass)
    await wireless_clients.async_load()

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the UniFi component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    controller = UniFiController(hass, config_entry)

    if not await controller.async_setup():
        return False

    controller_id = get_controller_id_from_config_entry(config_entry)
    hass.data[DOMAIN][controller_id] = controller

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, controller.shutdown)

    if controller.mac is None:
        return True

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, controller.mac)},
        manufacturer=ATTR_MANUFACTURER,
        model="UniFi Controller",
        name="UniFi Controller",
        # sw_version=config.raw['swversion'],
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    controller_id = get_controller_id_from_config_entry(config_entry)
    controller = hass.data[DOMAIN].pop(controller_id)
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
        data = self.data.get(controller_id, {"wireless_devices": []})
        return set(data["wireless_devices"])

    @callback
    def update_data(self, data, config_entry):
        """Update data and schedule to save to file."""
        controller_id = get_controller_id_from_config_entry(config_entry)
        self.data[controller_id] = {"wireless_devices": list(data)}

        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self):
        """Return data of UniFi wireless clients to store in a file."""
        return self.data
