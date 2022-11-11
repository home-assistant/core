"""Integration to UniFi Network and its various features."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN as UNIFI_DOMAIN, PLATFORMS, UNIFI_WIRELESS_CLIENTS
from .controller import UniFiController, get_unifi_controller
from .errors import AuthenticationRequired, CannotConnect
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

    # Removal of legacy PoE control was introduced with 2022.12
    async_remove_poe_client_entities(hass, config_entry)

    try:
        api = await get_unifi_controller(hass, config_entry.data)
        controller = UniFiController(hass, config_entry, api)
        await controller.initialize()

    except CannotConnect as err:
        raise ConfigEntryNotReady from err

    except AuthenticationRequired as err:
        raise ConfigEntryAuthFailed from err

    hass.data[UNIFI_DOMAIN][config_entry.entry_id] = controller
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    await controller.async_update_device_registry()

    if len(hass.data[UNIFI_DOMAIN]) == 1:
        async_setup_services(hass)

    api.start_websocket()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, controller.shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controller = hass.data[UNIFI_DOMAIN].pop(config_entry.entry_id)

    if not hass.data[UNIFI_DOMAIN]:
        async_unload_services(hass)

    return await controller.async_reset()


@callback
def async_remove_poe_client_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Remove PoE client entities."""
    ent_reg = er.async_get(hass)

    entity_ids_to_be_removed = [
        entry.entity_id
        for entry in ent_reg.entities.values()
        if entry.config_entry_id == config_entry.entry_id
        and entry.unique_id.startswith("poe-")
    ]

    for entity_id in entity_ids_to_be_removed:
        ent_reg.async_remove(entity_id)


class UnifiWirelessClients:
    """Class to store clients known to be wireless.

    This is needed since wireless devices going offline might get marked as wired by UniFi.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up client storage."""
        self.hass = hass
        self.data: dict[str, dict[str, list[str]]] = {}
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load data from file."""
        if (data := await self._store.async_load()) is not None:
            self.data = data

    @callback
    def get_data(self, config_entry: ConfigEntry) -> set[str]:
        """Get data related to a specific controller."""
        data = self.data.get(config_entry.entry_id, {"wireless_devices": []})
        return set(data["wireless_devices"])

    @callback
    def update_data(self, data: set[str], config_entry: ConfigEntry) -> None:
        """Update data and schedule to save to file."""
        self.data[config_entry.entry_id] = {"wireless_devices": list(data)}
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, dict[str, list[str]]]:
        """Return data of UniFi wireless clients to store in a file."""
        return self.data
