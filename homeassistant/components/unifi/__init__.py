"""Integration to UniFi Network and its various features."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_MANUFACTURER,
    CONF_CONTROLLER,
    DOMAIN as UNIFI_DOMAIN,
    LOGGER,
    UNIFI_WIRELESS_CLIENTS,
)
from .controller import UniFiController
from .services import async_setup_services, async_unload_services

SAVE_DELAY = 10
STORAGE_KEY = "unifi_data"
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Integration doesn't support configuration through configuration.yaml."""
    hass.data[UNIFI_WIRELESS_CLIENTS] = wireless_clients = UnifiWirelessClients(hass)
    await wireless_clients.async_load()

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the UniFi Network integration."""
    hass.data.setdefault(UNIFI_DOMAIN, {})

    # Flat configuration was introduced with 2021.3
    await async_flatten_entry_data(hass, config_entry)

    controller = UniFiController(hass, config_entry)
    if not await controller.async_setup():
        return False

    # Unique ID was introduced with 2021.3
    if config_entry.unique_id is None:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=controller.site_id
        )

    if not hass.data[UNIFI_DOMAIN]:
        async_setup_services(hass)

    hass.data[UNIFI_DOMAIN][config_entry.entry_id] = controller

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, controller.shutdown)
    )

    LOGGER.debug("UniFi Network config options %s", config_entry.options)

    if controller.mac is None:
        return True

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        configuration_url=controller.api.url,
        connections={(CONNECTION_NETWORK_MAC, controller.mac)},
        default_manufacturer=ATTR_MANUFACTURER,
        default_model="UniFi Network",
        default_name="UniFi Network",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controller = hass.data[UNIFI_DOMAIN].pop(config_entry.entry_id)

    if not hass.data[UNIFI_DOMAIN]:
        async_unload_services(hass)

    return await controller.async_reset()


async def async_flatten_entry_data(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Simpler configuration structure for entry data.

    Keep controller key layer in case user rollbacks.
    """

    data: dict = {**config_entry.data, **config_entry.data[CONF_CONTROLLER]}
    if config_entry.data != data:
        hass.config_entries.async_update_entry(config_entry, data=data)


class UnifiWirelessClients:
    """Class to store clients known to be wireless.

    This is needed since wireless devices going offline might get marked as wired by UniFi.
    """

    def __init__(self, hass):
        """Set up client storage."""
        self.hass = hass
        self.data = {}
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self):
        """Load data from file."""
        if (data := await self._store.async_load()) is not None:
            self.data = data

    @callback
    def get_data(self, config_entry):
        """Get data related to a specific controller."""
        data = self.data.get(config_entry.entry_id, {"wireless_devices": []})
        return set(data["wireless_devices"])

    @callback
    def update_data(self, data, config_entry):
        """Update data and schedule to save to file."""
        self.data[config_entry.entry_id] = {"wireless_devices": list(data)}
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self):
        """Return data of UniFi wireless clients to store in a file."""
        return self.data
