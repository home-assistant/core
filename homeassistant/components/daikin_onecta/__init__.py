"""Platform for the Daikin AC."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .const import DOMAIN
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator

PLATFORMS = [
    Platform.CLIMATE,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> None:
    """Establish connection with Daikin."""
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, config_entry
            )
        )
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, implementation)
    config_entry.runtime_data = coordinator

    await config_entry.runtime_data.async_config_entry_first_refresh()
    coordinator.async_register_devices()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DaikinOnectaConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
