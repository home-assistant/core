"""The HDFury Integration."""

from dataclasses import dataclass

from hdfury import HDFuryAPI, HDFuryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import HDFuryConfigCoordinator, HDFuryInfoCoordinator

PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass(kw_only=True)
class HDFuryRuntimeData:
    """Runtime data for HDFury integration."""

    client: HDFuryAPI
    host: str
    board: dict[str, str]
    info_coordinator: HDFuryInfoCoordinator
    config_coordinator: HDFuryConfigCoordinator


type HDFuryConfigEntry = ConfigEntry[HDFuryRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: HDFuryConfigEntry) -> bool:
    """Set up HDFury as config entry."""

    host: str = entry.data[CONF_HOST]
    client = HDFuryAPI(host, async_get_clientsession(hass))

    try:
        board = await client.get_board()
    except HDFuryError as error:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
        ) from error

    info_coordinator = HDFuryInfoCoordinator(hass, entry, client)
    config_coordinator = HDFuryConfigCoordinator(hass, entry, client)

    await info_coordinator.async_config_entry_first_refresh()
    await config_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = HDFuryRuntimeData(
        client=client,
        host=host,
        board=board,
        info_coordinator=info_coordinator,
        config_coordinator=config_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HDFuryConfigEntry) -> bool:
    """Unload a HDFury config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
