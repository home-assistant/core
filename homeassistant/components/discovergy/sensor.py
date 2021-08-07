"""Discovergy sensor entity."""
import logging

from pydiscovergy import Discovergy
from pydiscovergy.error import HTTPError
from pydiscovergy.models import Meter

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, ELECTRICITY_SENSORS, MANUFACTURER, MIN_TIME_BETWEEN_UPDATES

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


def get_coordinator_for_meter(
    hass: HomeAssistant, meter: Meter, discovergy_instance: Discovergy
) -> DataUpdateCoordinator:
    """Create a new DataUpdateCoordinator for given meter."""

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await discovergy_instance.get_last_reading(meter.get_meter_id())
        except HTTPError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    return coordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Discovergy sensors."""
    discovergy_instance = hass.data[DOMAIN][entry.entry_id]
    meters = await discovergy_instance.get_meters()

    entities = []
    for meter in meters:
        if meter.measurement_type == "ELECTRICITY":
            # Get coordinator for meter and fetch initial data so we have data when entities are added
            coordinator = get_coordinator_for_meter(hass, meter, discovergy_instance)
            await coordinator.async_config_entry_first_refresh()

            for value, description in ELECTRICITY_SENSORS.items():
                entities.append(
                    DiscovergyElectricitySensor(value, description, meter, coordinator)
                )

    async_add_entities(entities, False)


class DiscovergyElectricitySensor(CoordinatorEntity, SensorEntity):
    """Represents a discovergy electricity smart meter sensor."""

    def __init__(
        self,
        value: str,
        description: SensorEntityDescription,
        meter: Meter,
        coordinator: DataUpdateCoordinator,
    ):
        """Initialize the sensor."""
        self._value = value
        self._meter = meter
        self.coordinator = coordinator

        self.entity_description = description
        self._attr_name = (
            f"{self._meter.measurement_type} "
            f"{self._meter.location.street} "
            f"{self._meter.location.street_number} - "
            f"{self.entity_description.name}"
        )
        self._attr_unique_id = (
            f"{self._meter.serial_number}-" f"{self.entity_description.key}"
        )
        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, self._meter.get_meter_id())},
            ATTR_NAME: self.device_name,
            ATTR_MODEL: f"{self._meter.type} {self._meter.measurement_type}",
            ATTR_MANUFACTURER: MANUFACTURER,
        }

    @property
    def device_name(self):
        """Return the name of the actual physical meter."""
        return (
            f"{self._meter.type} ",
            f"{self._meter.measurement_type} ",
            f"{self._meter.location.street} " f"{self._meter.location.street_number}",
        )

    @property
    def state(self) -> StateType:
        """Return the sensor state."""
        if self.coordinator.data:
            if self._value == "energy":
                return self.coordinator.data.values[self._value] / 10000000000
            else:
                return self.coordinator.data.values[self._value] / 1000

        return None
