"""The BSB-Lan integration."""

import dataclasses

from bsblan import (
    BSBLAN,
    BSBLANAuthError,
    BSBLANConfig,
    BSBLANConnectionError,
    BSBLANError,
    Device,
    Info,
    StaticState,
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
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PASSKEY
from .coordinator import BSBLanUpdateCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]

type BSBLanConfigEntry = ConfigEntry[BSBLanData]


@dataclasses.dataclass
class BSBLanData:
    """BSBLan data stored in the Home Assistant data object."""

    coordinator: BSBLanUpdateCoordinator
    client: BSBLAN
    device: Device
    info: Info
    static: StaticState


async def async_setup_entry(hass: HomeAssistant, entry: BSBLanConfigEntry) -> bool:
    """Set up BSB-Lan from a config entry."""

    # create config using BSBLANConfig
    config = BSBLANConfig(
        host=entry.data[CONF_HOST],
        passkey=entry.data[CONF_PASSKEY],
        port=entry.data[CONF_PORT],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    # create BSBLAN client
    session = async_get_clientsession(hass)
    bsblan = BSBLAN(config, session)

    # Create and perform first refresh of the coordinator
    coordinator = BSBLanUpdateCoordinator(hass, entry, bsblan)
    await coordinator.async_config_entry_first_refresh()

    try:
        # Fetch all required data sequentially
        device = await bsblan.device()
        info = await bsblan.info()
        static = await bsblan.static_values()
    except BSBLANConnectionError as err:
        raise ConfigEntryNotReady(
            f"Failed to retrieve static device data from BSB-Lan device at {entry.data[CONF_HOST]}"
        ) from err
    except BSBLANAuthError as err:
        raise ConfigEntryAuthFailed(
            "Authentication failed while retrieving static device data"
        ) from err
    except BSBLANError as err:
        raise ConfigEntryError(
            "An unknown error occurred while retrieving static device data"
        ) from err

    entry.runtime_data = BSBLanData(
        client=bsblan,
        coordinator=coordinator,
        device=device,
        info=info,
        static=static,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BSBLanConfigEntry) -> bool:
    """Unload BSBLAN config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
