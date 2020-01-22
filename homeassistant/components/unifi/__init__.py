"""Support for devices connected to UniFi POE."""
import voluptuous as vol

from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .config_flow import get_controller_id_from_config_entry
from .const import (
    ATTR_MANUFACTURER,
    CONF_BLOCK_CLIENT,
    CONF_DETECTION_TIME,
    CONF_DONT_TRACK_CLIENTS,
    CONF_DONT_TRACK_DEVICES,
    CONF_DONT_TRACK_WIRED_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    DOMAIN,
    UNIFI_CONFIG,
    UNIFI_WIRELESS_CLIENTS,
)
from .controller import UniFiController

SAVE_DELAY = 10
STORAGE_KEY = "unifi_data"
STORAGE_VERSION = 1

CONF_CONTROLLERS = "controllers"

CONTROLLER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_SITE_ID): cv.string,
        vol.Optional(CONF_BLOCK_CLIENT, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_DONT_TRACK_CLIENTS): cv.boolean,
        vol.Optional(CONF_DONT_TRACK_DEVICES): cv.boolean,
        vol.Optional(CONF_DONT_TRACK_WIRED_CLIENTS): cv.boolean,
        vol.Optional(CONF_DETECTION_TIME): cv.positive_int,
        vol.Optional(CONF_SSID_FILTER): vol.All(cv.ensure_list, [cv.string]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONTROLLERS): vol.All(
                    cv.ensure_list, [CONTROLLER_SCHEMA]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    hass.data[UNIFI_CONFIG] = []

    if DOMAIN in config:
        hass.data[UNIFI_CONFIG] = config[DOMAIN][CONF_CONTROLLERS]

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

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, controller.shutdown)

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
