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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PASSKEY, DOMAIN
from .coordinator import BSBLanFastCoordinator, BSBLanSlowCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type BSBLanConfigEntry = ConfigEntry[BSBLanData]


@dataclasses.dataclass
class BSBLanData:
    """BSBLan data stored in the Home Assistant data object."""

    fast_coordinator: BSBLanFastCoordinator
    slow_coordinator: BSBLanSlowCoordinator
    client: BSBLAN
    device: Device
    info: Info
    static: StaticState


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the BSB-Lan integration."""
    async_setup_services(hass)
    return True


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

    try:
        # Initialize the client first - this sets up internal caches and validates the connection
        await bsblan.initialize()
        # Fetch all required device metadata
        device = await bsblan.device()
        info = await bsblan.info()
        static = await bsblan.static_values()
    except BSBLANConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    except BSBLANAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="setup_auth_error",
        ) from err
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_connection_error",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    except BSBLANError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_general_error",
        ) from err

    # Create coordinators with the already-initialized client
    fast_coordinator = BSBLanFastCoordinator(hass, entry, bsblan)
    slow_coordinator = BSBLanSlowCoordinator(hass, entry, bsblan)

    # Perform first refresh of both coordinators
    await fast_coordinator.async_config_entry_first_refresh()

    # Try to refresh slow coordinator, but don't fail if DHW is not available
    # This allows the integration to work even if the device doesn't support DHW
    await slow_coordinator.async_refresh()

    entry.runtime_data = BSBLanData(
        client=bsblan,
        fast_coordinator=fast_coordinator,
        slow_coordinator=slow_coordinator,
        device=device,
        info=info,
        static=static,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BSBLanConfigEntry) -> bool:
    """Unload BSBLAN config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
