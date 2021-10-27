"""Support for SRP Energy Sensor."""
import logging

import async_timeout
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
import homeassistant.util.dt as dt_util

from .const import (
    ATTRIBUTION,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
    SENSOR_TYPE_THIS_DAY,
    SENSORS_INFO,
    SOURCE_TYPE_COST,
    SOURCE_TYPE_USAGE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SRP Energy Usage sensor."""
    # API object stored here by __init__.py
    is_time_of_use = False
    api = hass.data[DOMAIN][entry.entry_id]
    if entry and entry.data:
        is_time_of_use = entry.data["is_tou"]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Fetch srp_energy data
            start_date = dt_util.now().replace(day=1)
            end_date = dt_util.now()
            with async_timeout.timeout(10):
                hourly_usage = await hass.async_add_executor_job(
                    api.usage,
                    start_date,
                    end_date,
                    is_time_of_use,
                )

                previous_daily_usage = 0.0
                previous_daily_cost = 0.0
                for _, _, _, kwh, cost in hourly_usage:
                    previous_daily_usage += float(kwh)
                    previous_daily_cost += float(cost)

                data = {
                    SOURCE_TYPE_USAGE: {
                        SENSOR_TYPE_THIS_DAY: previous_daily_usage,
                    },
                    SOURCE_TYPE_COST: {
                        SENSOR_TYPE_THIS_DAY: previous_daily_cost,
                    },
                }

                return data
        except (TimeoutError) as timeout_err:
            raise UpdateFailed("Timeout communicating with API") from timeout_err
        except (ConnectError, HTTPError, Timeout, ValueError, TypeError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for sensor_info in SENSORS_INFO:
        sensor = SrpEnergySensor(coordinator, **sensor_info)
        entities.append(sensor)

    async_add_entities(entities)


class SrpEnergySensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Srp Energy sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator,
        name,
        device_class,
        unit_of_measurement,
        source_type,
        sensor_type,
        icon,
        precision,
        state_class,
    ):
        """Initialize the SrpEntity class."""
        super().__init__(coordinator)
        self._name = name
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self._source_type = source_type
        self._sensor_type = sensor_type
        self._icon = icon
        self._precision = precision
        self._attr_state_class = state_class
        self._attibution = ATTRIBUTION

    @property
    def unique_id(self):
        """Return an unique id for the sensor."""
        return f"{DOMAIN}_{self._source_type}_{self._sensor_type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data[self._source_type][self._sensor_type] is not None:
            return round(
                self.coordinator.data[self._source_type][self._sensor_type],
                self._precision,
            )
        return None

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use for the sensor."""
        return self._icon

    @property
    def available(self):
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data
            and self._source_type in self.coordinator.data
            and self.coordinator.data[self._source_type]
        )
