"""The Homewizard Energy integration."""
import asyncio
import logging

import aiohwenergy
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_API, COORDINATOR, DOMAIN, PLATFORMS
from .coordinator import HWEnergyDeviceUpdateCoordinator as Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homewizard Energy from a config entry."""

    _LOGGER.debug("__init__ async_setup_entry")

    # Get api and do a initialization
    energy_api = aiohwenergy.HomeWizardEnergy(entry.data.get("host"))

    # Validate connection
    initialized = False
    try:
        with async_timeout.timeout(10):
            await energy_api.initialize()
            initialized = True

    except (asyncio.TimeoutError, aiohwenergy.RequestError) as ex:
        _LOGGER.error(
            "Error connecting to the Energy device at %s",
            energy_api.host,
        )
        raise ConfigEntryNotReady from ex

    except aiohwenergy.DisabledError as ex:
        _LOGGER.error("API disabled, API must be enabled in the app")
        raise ConfigEntryNotReady from ex

    except aiohwenergy.AiohwenergyException as ex:
        _LOGGER.error("Unknown Energy API error occurred")
        raise ConfigEntryNotReady from ex

    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error(
            "Unknown error connecting with Energy Device at %s",
            energy_api.host,
        )
        raise ConfigEntryNotReady from ex

    finally:
        if not initialized:
            await energy_api.close()

    # Create coordinator
    coordinator = Coordinator(hass, energy_api)
    await coordinator.async_config_entry_first_refresh()

    # Finalize
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.data["unique_id"]] = {
        COORDINATOR: coordinator,
        CONF_API: energy_api,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("__init__ async_unload_entry")

    unload_ok = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            )
        )
    )

    if unload_ok:
        config_data = hass.data[DOMAIN].pop(entry.data["unique_id"])
        if "api" in config_data:
            energy_api = config_data[CONF_API]
            await energy_api.close()

    return unload_ok
