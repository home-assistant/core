"""DataUpdateCoordinator for Plugwise."""
from datetime import timedelta

from plugwise import PlugwiseData, Smile
from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    InvalidXMLError,
    ResponseError,
    UnsupportedDeviceError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_USERNAME, DOMAIN, LOGGER


def _async_cleanup_registry_entries(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entry_id: str,
    current_entities: set[tuple[Platform, str]],
) -> None:
    """Remove extra entities that are no longer part of the integration."""
    entity_registry = er.async_get(hass)

    existing_entries = er.async_entries_for_config_entry(entity_registry, entry_id)
    entities = {
        (entity.domain, entity.unique_id): entity.entity_id
        for entity in existing_entries
    }

    extra_entities = set(entities.keys()).difference(current_entities)
    if not extra_entities:
        return

    for entity in extra_entities:
        if entity_registry.async_is_registered(entities[entity]):
            entity_registry.async_remove(entities[entity])

    LOGGER.debug(
        ("Clean-up of Plugwise entities: %s entities removed for config entry %s"),
        len(extra_entities),
        entry_id,
    )


class PlugwiseDataUpdateCoordinator(DataUpdateCoordinator[PlugwiseData]):
    """Class to manage fetching Plugwise data from single endpoint."""

    _connected: bool = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            # Don't refresh immediately, give the device time to process
            # the change in state before we query it.
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=1.5,
                immediate=False,
            ),
        )

        self.api = Smile(
            host=entry.data[CONF_HOST],
            username=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
            password=entry.data[CONF_PASSWORD],
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
            timeout=30,
            websession=async_get_clientsession(hass, verify_ssl=False),
        )
        self.current_entities: set[tuple[Platform, str]] = {
            (Platform.CLIMATE, "dummy_id-climate")
        }

    async def _connect(self) -> None:
        """Connect to the Plugwise Smile."""
        self._connected = await self.api.connect()
        self.api.get_all_devices()
        self.update_interval = DEFAULT_SCAN_INTERVAL.get(
            str(self.api.smile_type), timedelta(seconds=60)
        )

    async def _async_update_data(self) -> PlugwiseData:
        """Fetch data from Plugwise."""

        try:
            if not self._connected:
                await self._connect()
            data = await self.api.async_update()
        except InvalidAuthentication as err:
            raise ConfigEntryError("Invalid username or Smile ID") from err
        except (InvalidXMLError, ResponseError) as err:
            raise UpdateFailed(
                "Invalid XML data, or error indication received for the Plugwise"
                " Adam/Smile/Stretch"
            ) from err
        except UnsupportedDeviceError as err:
            raise ConfigEntryError("Device with unsupported firmware") from err
        except ConnectionFailedError as err:
            raise UpdateFailed("Failed to connect to the Plugwise Smile") from err
        return data
