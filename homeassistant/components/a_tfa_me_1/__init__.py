"""TFA.me station integration: ___init___.py."""

# from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_INTERVAL, CONF_MULTIPLE_ENTITIES, DOMAIN
from .coordinator import TFAmeDataCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


# ---- TFA.me station setup ----
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:  # TFAmeConfigEntry) -> bool:
    """Set up a TFA.me station."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_IP_ADDRESS]
    up_interval = entry.data[CONF_INTERVAL]
    # Get option for alter user changes
    interval_opt = entry.options.get(CONF_INTERVAL, -1)
    if interval_opt != -1:
        up_interval = interval_opt
    # Update time
    msg: str = "Pull interval: " + str(up_interval)
    _LOGGER.info(msg)
    delta_interval = timedelta(seconds=up_interval)

    # Use multiple entities
    multiple_entities = entry.data[CONF_MULTIPLE_ENTITIES]

    # DataUpdateCoordinator for cyclic requests
    coordinator = TFAmeDataCoordinator(
        hass, entry, host, delta_interval, multiple_entities
    )

    # Register listener for option changes
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    # Save coordinator for later usage
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # First request for sensor data
    await coordinator.async_config_entry_first_refresh()

    # Save coordinator
    entry.runtime_data = coordinator

    assert entry.unique_id

    _LOGGER.debug("Setting up platforms")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Get running instances
    instances = await get_instances(hass)
    msg = f"Instances: {len(instances)}"
    _LOGGER.info(msg)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
    # return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# ---- Options update listener: option is pull/request interval ----
async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Will be called when options are changed."""

    reset_rain = entry.options.get("action_rain", False)
    msg: str = "Options 'reset rain': " + str(reset_rain)
    _LOGGER.info(msg)

    new_interval = entry.options.get(CONF_INTERVAL, 10)
    msg = "Options 'pull interval': " + str(new_interval)
    _LOGGER.info(msg)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.update_interval = timedelta(seconds=new_interval)

    await coordinator.async_refresh()


async def get_instances(hass: HomeAssistant):
    """Find all instances of this integration."""
    return hass.config_entries.async_entries(DOMAIN)


async def get_running_instances(hass: HomeAssistant):
    """Find all running instances of this integration."""
    entries = hass.config_entries.async_entries(DOMAIN)

    # Verifies whether integration is active or not.
    running_instances: list[ConfigEntry] = [
        entry for entry in entries if entry.state == ConfigEntryState.LOADED
    ]

    return running_instances
