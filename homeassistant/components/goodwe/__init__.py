"""The Goodwe inverter component."""
from datetime import timedelta
import logging

from goodwe import InverterError, RequestFailedException, connect

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MODEL_FAMILY,
    CONF_NETWORK_RETRIES,
    CONF_NETWORK_TIMEOUT,
    DEFAULT_NETWORK_RETRIES,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_INVERTER,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Goodwe components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    name = entry.title
    host = entry.data[CONF_HOST]
    model_family = entry.data[CONF_MODEL_FAMILY]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    network_retries = entry.options.get(CONF_NETWORK_RETRIES, DEFAULT_NETWORK_RETRIES)
    network_timeout = entry.options.get(CONF_NETWORK_TIMEOUT, DEFAULT_NETWORK_TIMEOUT)

    # Connect to Goodwe inverter
    try:
        inverter = await connect(
            host=host,
            family=model_family,
            comm_addr=0,
            timeout=network_timeout,
            retries=network_retries,
        )
    except InverterError as err:
        raise ConfigEntryNotReady from err

    async def async_update_data():
        """Fetch data from the inverter."""
        try:
            data = await inverter.read_runtime_data()
        except RequestFailedException as ex:
            # UDP communication with inverter is by definition unreliable.
            # It is rather normal in many environments to fail to receive
            # proper response in usual time, so we intentionally report
            # failures only after consecutive streak of 3 of them.
            if ex.consecutive_failures_count < 3:
                # return empty dictionary
                # sensors will keep their previous values
                _LOGGER.debug(f"Request failed (#{ex.consecutive_failures_count}).")
                return {}
            else:
                # return None
                # sensors will report themselves as not available
                _LOGGER.debug(
                    f"Inverter not responding (#{ex.consecutive_failures_count})."
                )
                return None
        except InverterError as ex:
            raise UpdateFailed(ex) from ex

        return data

    # Create update coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=scan_interval),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_INVERTER: inverter,
        KEY_COORDINATOR: coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
