"""The Tesla Powerwall integration."""
import asyncio
from datetime import timedelta
import logging

import requests
from tesla_powerwall import MissingAttributeError, Powerwall, PowerwallUnreachableError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    POWERWALL_API_CHANGED,
    POWERWALL_API_CHARGE,
    POWERWALL_API_DEVICE_TYPE,
    POWERWALL_API_GRID_STATUS,
    POWERWALL_API_METERS,
    POWERWALL_API_SERIAL_NUMBERS,
    POWERWALL_API_SITE_INFO,
    POWERWALL_API_SITEMASTER,
    POWERWALL_API_STATUS,
    POWERWALL_COORDINATOR,
    POWERWALL_HTTP_SESSION,
    POWERWALL_OBJECT,
    UPDATE_INTERVAL,
)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)

PLATFORMS = ["binary_sensor", "sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tesla Powerwall component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def _migrate_old_unique_ids(hass, entry_id, powerwall_data):
    serial_numbers = powerwall_data[POWERWALL_API_SERIAL_NUMBERS]
    site_info = powerwall_data[POWERWALL_API_SITE_INFO]

    @callback
    def _async_migrator(entity_entry: entity_registry.RegistryEntry):
        parts = entity_entry.unique_id.split("_")
        # Check if the unique_id starts with the serial_numbers of the powerwalls
        if parts[0 : len(serial_numbers)] != serial_numbers:
            # The old unique_id ended with the nomianal_system_engery_kWh so we can use that
            # to find the old base unique_id and extract the device_suffix.
            normalized_energy_index = (
                len(parts) - 1 - parts[::-1].index(str(site_info.nominal_system_energy))
            )
            device_suffix = parts[normalized_energy_index + 1 :]

            new_unique_id = "_".join([*serial_numbers, *device_suffix])
            _LOGGER.info(
                "Migrating unique_id from [%s] to [%s]",
                entity_entry.unique_id,
                new_unique_id,
            )
            return {"new_unique_id": new_unique_id}
        return None

    await entity_registry.async_migrate_entries(hass, entry_id, _async_migrator)


async def _async_handle_api_changed_error(
    hass: HomeAssistant, error: MissingAttributeError
):
    # The error might include some important information about what exactly changed.
    _LOGGER.error(str(error))
    hass.components.persistent_notification.async_create(
        "It seems like your powerwall uses an unsupported version. "
        "Please update the software of your powerwall or if it is "
        "already the newest consider reporting this issue.\nSee logs for more information",
        title="Unknown powerwall software version",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tesla Powerwall from a config entry."""

    entry_id = entry.entry_id

    hass.data[DOMAIN].setdefault(entry_id, {})
    http_session = requests.Session()
    power_wall = Powerwall(entry.data[CONF_IP_ADDRESS], http_session=http_session)
    try:
        await hass.async_add_executor_job(power_wall.detect_and_pin_version)
        await hass.async_add_executor_job(_fetch_powerwall_data, power_wall)
        powerwall_data = await hass.async_add_executor_job(call_base_info, power_wall)
    except PowerwallUnreachableError as err:
        http_session.close()
        raise ConfigEntryNotReady from err
    except MissingAttributeError as err:
        http_session.close()
        await _async_handle_api_changed_error(hass, err)
        return False

    await _migrate_old_unique_ids(hass, entry_id, powerwall_data)

    async def async_update_data():
        """Fetch data from API endpoint."""
        # Check if we had an error before
        _LOGGER.debug("Checking if update failed")
        if not hass.data[DOMAIN][entry.entry_id][POWERWALL_API_CHANGED]:
            _LOGGER.debug("Updating data")
            try:
                return await hass.async_add_executor_job(
                    _fetch_powerwall_data, power_wall
                )
            except PowerwallUnreachableError as err:
                raise UpdateFailed("Unable to fetch data from powerwall") from err
            except MissingAttributeError as err:
                await _async_handle_api_changed_error(hass, err)
                hass.data[DOMAIN][entry.entry_id][POWERWALL_API_CHANGED] = True
                # Returns the cached data. This data can also be None
                return hass.data[DOMAIN][entry.entry_id][POWERWALL_COORDINATOR].data
        else:
            return hass.data[DOMAIN][entry.entry_id][POWERWALL_COORDINATOR].data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Powerwall site",
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    hass.data[DOMAIN][entry.entry_id] = powerwall_data
    hass.data[DOMAIN][entry.entry_id].update(
        {
            POWERWALL_OBJECT: power_wall,
            POWERWALL_COORDINATOR: coordinator,
            POWERWALL_HTTP_SESSION: http_session,
            POWERWALL_API_CHANGED: False,
        }
    )

    await coordinator.async_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


def call_base_info(power_wall):
    """Wrap powerwall properties to be a callable."""
    serial_numbers = power_wall.get_serial_numbers()
    # Make sure the serial numbers always have the same order
    serial_numbers.sort()
    return {
        POWERWALL_API_SITE_INFO: power_wall.get_site_info(),
        POWERWALL_API_STATUS: power_wall.get_status(),
        POWERWALL_API_DEVICE_TYPE: power_wall.get_device_type(),
        POWERWALL_API_SERIAL_NUMBERS: serial_numbers,
    }


def _fetch_powerwall_data(power_wall):
    """Process and update powerwall data."""
    return {
        POWERWALL_API_CHARGE: power_wall.get_charge(),
        POWERWALL_API_SITEMASTER: power_wall.get_sitemaster(),
        POWERWALL_API_METERS: power_wall.get_meters(),
        POWERWALL_API_GRID_STATUS: power_wall.get_grid_status(),
    }


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][entry.entry_id][POWERWALL_HTTP_SESSION].close()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
