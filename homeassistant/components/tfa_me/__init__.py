"""TFA.me station integration: ___init___.py."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_MULTIPLE_ENTITIES, DOMAIN, LOCAL_POLL_INTERVAL
from .coordinator import TFAmeConfigEntry, TFAmeDataCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TFAmeConfigEntry) -> bool:
    """Set up a TFA.me station."""
    # Get IP or station ID
    host = entry.data[CONF_IP_ADDRESS]
    # Use default poll interval
    delta_interval = timedelta(seconds=LOCAL_POLL_INTERVAL)

    # Use multiple entities option
    multiple_entities = entry.data[CONF_MULTIPLE_ENTITIES]

    # New DataUpdateCoordinator for cyclic requests
    coordinator = TFAmeDataCoordinator(
        hass, entry, host, delta_interval, multiple_entities
    )

    # Register listener for option changes
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    # Save coordinator for later usage
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # First request for sensor data
    await coordinator.async_config_entry_first_refresh()

    # Set coordinator data
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


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Will be called when options are changed via UI."""

    reset_rain = entry.options.get("action_rain", False)
    msg: str = "Options 'reset rain': " + str(reset_rain)
    _LOGGER.info(msg)

    coordinator = hass.data[DOMAIN][entry.entry_id]

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
