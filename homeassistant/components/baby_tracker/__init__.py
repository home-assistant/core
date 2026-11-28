"""Baby Tracker (Nighp)."""

from pybabytracker import BabyTrackerClient

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store

from .const import CONF_DEVICE_UUID, DEVICE_NAME, STORAGE_VERSION
from .coordinator import BabyTrackerConfigEntry, BabyTrackerCoordinator, storage_key

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BabyTrackerConfigEntry,
) -> None:
    """Sign in, load or backfill the records, and set up the sensors."""
    # The service authenticates by cookie, so this client gets a session of its own.
    session = async_create_clientsession(hass)
    client = BabyTrackerClient(
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_DEVICE_UUID],
        DEVICE_NAME,
        session=session,
    )
    # Runs on unload and also when setup fails, so the client is never left open.
    entry.async_on_unload(client.close)
    coordinator = BabyTrackerCoordinator(hass, entry, client, session)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BabyTrackerConfigEntry,
) -> None:
    """Unload the platforms. The coordinator stops and the client closes through the entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: BabyTrackerConfigEntry
) -> None:
    """Delete what the entry saved."""
    await Store(hass, STORAGE_VERSION, storage_key(entry.entry_id)).async_remove()
