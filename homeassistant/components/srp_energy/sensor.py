"""Support for SRP Energy Sensor."""
from __future__ import annotations

from datetime import timedelta

import async_timeout
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
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
    entry_unique_id: str = getattr(entry, "unique_id", DEFAULT_NAME)
    is_time_of_use: bool = False
    if entry and entry.data:
        api = hass.data[DOMAIN][entry.entry_id]
        is_time_of_use = entry.data["is_tou"]

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

            async with async_timeout.timeout(10):
                hourly_usage = await hass.async_add_executor_job(
                    api.usage,
                    start_date,
                    end_date,
                    is_time_of_use,
                )

                LOGGER.debug(
                    "async_update_data: Received %s records from %s to %s",
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
        except (TimeoutError) as timeout_err:
            raise UpdateFailed("Timeout communicating with API") from timeout_err
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
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([SrpEntity(coordinator, entry_unique_id)])


class SrpEntity(SensorEntity):
    """Implementation of a Srp Energy Usage sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, coordinator, entry_unique_id):
        """Initialize the SrpEntity class."""
        self._name = SENSOR_NAME
        self.type = SENSOR_TYPE
        self.coordinator = coordinator
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._state = None
        unique_id = f"{entry_unique_id}_energy_usage".lower()

        LOGGER.debug("Setting entity name %s", unique_id)
        self._attr_unique_id = unique_id

        self._attr_native_value = self.coordinator.data

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{DEFAULT_NAME} {self._name}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        LOGGER.debug(
            "Reading entity native_value %s at %s",
            self.coordinator.data,
            dt_util.now(),
        )
        return self.coordinator.data

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self) -> str:
        """Return icon."""
        return ICON

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> str:
        """Return the state class."""
        return SensorStateClass.TOTAL_INCREASING

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
        if self.coordinator.data:
            self._state = self.coordinator.data

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
