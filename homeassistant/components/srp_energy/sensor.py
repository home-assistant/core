"""Support for SRP Energy Sensor."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_IS_TOU,
    DEVICE_CONFIG_URL,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
    LOGGER,
    MIN_TIME_BETWEEN_UPDATES,
    PHOENIX_TIME_ZONE,
    SENSOR_NAME,
    SENSOR_TYPE,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SRP Energy Usage sensor."""
    # API object stored here by __init__.py
    api = hass.data[DOMAIN][entry.entry_id]
    is_time_of_use = entry.data[CONF_IS_TOU]
    config_name = entry.data[CONF_NAME]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        LOGGER.debug("async_update_data enter")
        try:
            # Fetch srp_energy data
            phx_time_zone = dt_util.get_time_zone(PHOENIX_TIME_ZONE)
            end_date = dt_util.now(phx_time_zone)
            start_date = end_date - timedelta(days=1)

            async with asyncio.timeout(10):
                hourly_usage = await hass.async_add_executor_job(
                    api.usage,
                    start_date,
                    end_date,
                    is_time_of_use,
                )

                LOGGER.debug(
                    "async_update_data: Received %s record(s) from %s to %s",
                    len(hourly_usage) if hourly_usage else "None",
                    start_date,
                    end_date,
                )

                previous_daily_usage = 0.0
                for _, _, _, kwh, _ in hourly_usage:
                    previous_daily_usage += float(kwh)

                LOGGER.debug(
                    "async_update_data: previous_daily_usage %s",
                    previous_daily_usage,
                )

                return previous_daily_usage
        except TimeoutError as timeout_err:
            raise UpdateFailed("Timeout communicating with API") from timeout_err
        except KeyError as missing_data_err:
            raise UpdateFailed(
                f"Verify account and credentials. Missing Data: {missing_data_err}"
            ) from missing_data_err
        except (ConnectError, HTTPError, Timeout, ValueError, TypeError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    async_add_entities(
        [
            SrpEntity(
                coordinator,
                config_name=config_name,
            )
        ]
    )


class SrpEntity(SensorEntity):
    """Implementation of a Srp Energy Usage sensor."""

    _attr_has_entity_name = True
    _attr_attribution = "Powered by SRP Energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_has_entity_name = True
    _attr_translation_key = "energy_usage"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_name: str,
    ) -> None:
        """Initialize the SrpEntity class."""
        self._name = SENSOR_NAME
        self.type = SENSOR_TYPE
        self.coordinator = coordinator
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._state = None
        self._config_name = config_name
        unique_id: str = f"{config_name}_energy_usage".lower()
        LOGGER.debug("Setting unique id %s", unique_id)
        self._attr_unique_id = unique_id

        # Configure device
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{config_name}_Energy usage")},
            configuration_url=DEVICE_CONFIG_URL,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_MODEL,
            name=f"{config_name} Energy consumption",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self.coordinator.data
