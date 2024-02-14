"""Integration to UniFi Network and its various features."""

from aiounifi.models.client import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN as UNIFI_DOMAIN, PLATFORMS, UNIFI_WIRELESS_CLIENTS
from .controller import UniFiController, get_unifi_controller
from .errors import AuthenticationRequired, CannotConnect
from .services import async_setup_services, async_unload_services

SAVE_DELAY = 10
STORAGE_KEY = "unifi_data"
STORAGE_VERSION = 1

CONFIG_SCHEMA = cv.config_entry_only_config_schema(UNIFI_DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Integration doesn't support configuration through configuration.yaml."""
    hass.data[UNIFI_WIRELESS_CLIENTS] = wireless_clients = UnifiWirelessClients(hass)
    await wireless_clients.async_load()

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the UniFi Network integration."""
    hass.data.setdefault(UNIFI_DOMAIN, {})

    try:
        api = await get_unifi_controller(hass, config_entry.data)

    except CannotConnect as err:
        raise ConfigEntryNotReady from err

    except AuthenticationRequired as err:
        raise ConfigEntryAuthFailed from err

    controller = UniFiController(hass, config_entry, api)
    await controller.initialize()
    hass.data[UNIFI_DOMAIN][config_entry.entry_id] = controller

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    controller.async_update_device_registry()

    if len(hass.data[UNIFI_DOMAIN]) == 1:
        async_setup_services(hass)

    controller.start_websocket()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, controller.shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controller: UniFiController = hass.data[UNIFI_DOMAIN].pop(config_entry.entry_id)

    if not hass.data[UNIFI_DOMAIN]:
        async_unload_services(hass)

    return await controller.async_reset()


class UnifiWirelessClients:
    """Class to store clients known to be wireless.

    This is needed since wireless devices going offline
    might get marked as wired by UniFi.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up client storage."""
        self.hass = hass
        self.data: dict[str, dict[str, list[str]] | list[str]] = {}
        self.wireless_clients: set[str] = set()
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load data from file."""
        if (data := await self._store.async_load()) is not None:
            self.data = data
            if "wireless_clients" not in data:
                data["wireless_clients"] = [
                    obj_id
                    for config_entry in data
                    for obj_id in data[config_entry]["wireless_devices"]
                ]
            self.wireless_clients.update(data["wireless_clients"])

    @callback
    def is_wireless(self, client: Client) -> bool:
        """Is client known to be wireless.

        Store if client is wireless and not known.
        """
        if not client.is_wired and client.mac not in self.wireless_clients:
            self.wireless_clients.add(client.mac)
            self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

        return client.mac in self.wireless_clients

    @callback
    def update_clients(self, clients: set[Client]) -> None:
        """Update data and schedule to save to file."""
        self.wireless_clients.update(
            {client.mac for client in clients if not client.is_wired}
        )
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, dict[str, list[str]] | list[str]]:
        """Return data of UniFi wireless clients to store in a file."""
        self.data["wireless_clients"] = list(self.wireless_clients)
        return self.data

    def __contains__(self, obj_id: int | str) -> bool:
        """Validate membership of item ID."""
        return obj_id in self.wireless_clients
