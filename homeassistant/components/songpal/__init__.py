"""The songpal component."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from songpal import Device, SongpalException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_ENDPOINT, DOMAIN
from .coordinator import SongpalCoordinator

_LOGGER = logging.getLogger(__name__)

SONGPAL_CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(CONF_NAME): cv.string, vol.Required(CONF_ENDPOINT): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [SONGPAL_CONFIG_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.MEDIA_PLAYER,
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: Any | None = None,
) -> None:
    """Set up from legacy configuration file. Obsolete."""
    _LOGGER.error(
        "Configuring Songpal through media_player platform is no longer supported."
        " Convert to songpal platform or UI configuration"
    )


@dataclass
class RuntimeData:
    """Class to hold data that should be easily accessible throughout the integration."""

    coordinator: SongpalCoordinator


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up songpal environment."""
    if (conf := config.get(DOMAIN)) is None:
        return True
    for config_entry in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config_entry,
            ),
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up songpal coordinator and entities."""

    _LOGGER.warning("Setup entry")

    name = entry.data[CONF_NAME]
    endpoint = entry.data[CONF_ENDPOINT]
    device = Device(endpoint)

    try:
        async with asyncio.timeout(
            10
        ):  # set timeout to avoid blocking the setup process
            await device.get_supported_methods()
    except (SongpalException, TimeoutError) as ex:
        _LOGGER.warning("[%s(%s)] Unable to connect", name, endpoint)
        _LOGGER.debug("Unable to get methods from songpal: %s", ex)
        raise UpdateFailed(f"[{name}({endpoint})] Unable to connect") from ex

    _LOGGER.warning("Setup coordinator")
    coordinator = SongpalCoordinator(hass, entry, name, device)

    _LOGGER.warning("First refresh")
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.warning("Refresh complete")
    if not coordinator.initialized:
        _LOGGER.warning("Coordinator not initialised")
        raise ConfigEntryNotReady

    _LOGGER.warning("Runtime data")
    entry.runtime_data = RuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload songpal media player."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
