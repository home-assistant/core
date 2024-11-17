"""The Playstation Network integration."""

from __future__ import annotations

from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError
from psnawp_api.psnawp import PSNAWP

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .coordinator import PlaystationNetworkCoordinator

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


type PlaystationNetworkConfigEntry = ConfigEntry[PlaystationNetworkCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Set up Playstation Network from a config entry."""

    try:
        psn = PSNAWP(entry.data["npsso"])
    except PSNAWPAuthenticationError as error:
        raise ConfigEntryAuthFailed(error) from error
    except Exception as ex:
        raise ConfigEntryNotReady(ex) from ex

    try:
        user = await hass.async_add_executor_job(lambda: psn.user(online_id="me"))
    except PSNAWPAuthenticationError as error:
        raise ConfigEntryAuthFailed(error) from error
    except Exception as ex:
        raise ConfigEntryNotReady(ex) from ex

    coordinator = PlaystationNetworkCoordinator(hass, user)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
