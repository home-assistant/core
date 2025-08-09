"""Integration to UniFi Network and its various features."""

from aiounifi.models.client import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CLIENT_SOURCE, DOMAIN, PLATFORMS, UNIFI_WIRELESS_CLIENTS
from .errors import AuthenticationRequired, CannotConnect
from .hub import UnifiHub, get_unifi_api
from .services import async_setup_services

type UnifiConfigEntry = ConfigEntry[UnifiHub]

SAVE_DELAY = 10
STORAGE_KEY = "unifi_data"
STORAGE_VERSION = 1

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Integration doesn't support configuration through configuration.yaml."""
    async_setup_services(hass)

    hass.data[UNIFI_WIRELESS_CLIENTS] = wireless_clients = UnifiWirelessClients(hass)
    await wireless_clients.async_load()

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: UnifiConfigEntry
) -> bool:
    """Set up the UniFi Network integration."""
    try:
        api = await get_unifi_api(hass, config_entry.data)

    except CannotConnect as err:
        raise ConfigEntryNotReady from err

    except AuthenticationRequired as err:
        raise ConfigEntryAuthFailed from err

    hub = config_entry.runtime_data = UnifiHub(hass, config_entry, api)
    await hub.initialize()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    hub.async_update_device_registry()
    hub.entity_loader.load_entities()

    hub.websocket.start()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hub.shutdown)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: UnifiConfigEntry
) -> bool:
    """Unload a config entry."""
    return await config_entry.runtime_data.async_reset()


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: UnifiConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove config entry from a device.

    Allow removal of devices to improve user experience.
    Users should be able to clean up their device registry.
    The device will be re-discovered if it's still active on the network.

    When a device is removed, also clean up tracking lists to prevent
    automatic re-addition if track new devices is disabled.
    """
    # Get MAC addresses from device connections
    mac_addresses = {
        identifier
        for connection_type, identifier in device_entry.connections
        if connection_type == "mac"
    }

    if mac_addresses:
        # Remove from wireless clients tracking
        wireless_clients = hass.data.get(UNIFI_WIRELESS_CLIENTS)
        if wireless_clients and hasattr(wireless_clients, "remove_clients"):
            wireless_clients.remove_clients(mac_addresses)

        # Remove from client source configuration to prevent re-addition
        current_options = dict(config_entry.options)
        client_sources = current_options.get(CONF_CLIENT_SOURCE, [])

        if client_sources:
            # Remove any matching MAC addresses from the client source list
            updated_sources = [
                mac for mac in client_sources if mac not in mac_addresses
            ]

            if len(updated_sources) != len(client_sources):
                # Update config entry options if changes were made
                current_options[CONF_CLIENT_SOURCE] = updated_sources
                hass.config_entries.async_update_entry(
                    config_entry, options=current_options
                )

    # Always allow device removal for better user experience
    return True


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
    def remove_clients(self, mac_addresses: set[str]) -> None:
        """Remove clients from tracking and schedule save to file."""
        for mac in mac_addresses:
            self.wireless_clients.discard(mac)
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, dict[str, list[str]] | list[str]]:
        """Return data of UniFi wireless clients to store in a file."""
        self.data["wireless_clients"] = list(self.wireless_clients)
        return self.data

    def __contains__(self, obj_id: int | str) -> bool:
        """Validate membership of item ID."""
        return obj_id in self.wireless_clients
