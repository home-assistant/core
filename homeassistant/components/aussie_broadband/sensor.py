"""Support for Aussie Broadband metric sensors."""
from datetime import timedelta
import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN
from ...core import HomeAssistant
from ..sensor import SensorEntity
from .const import ATTR_SERVICE_ID

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Aussie Broadband sensor from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    service_id = entry.data[ATTR_SERVICE_ID]

    async def async_update_data():
        return await hass.async_add_executor_job(client.get_usage, service_id)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_interval=UPDATE_INTERVAL,
        update_method=async_update_data,
    )
    await coordinator.async_refresh()

    async_add_entities(
        [
            CounterEntity(coordinator, service_id, "Total Usage", "usedMb", "MB"),
            CounterEntity(coordinator, service_id, "Downloaded", "downloadedMb", "MB"),
            CounterEntity(coordinator, service_id, "Uploaded", "uploadedMb", "MB"),
            CounterEntity(
                coordinator, service_id, "Billing Cycle Length", "daysTotal", "days"
            ),
            CounterEntity(
                coordinator,
                service_id,
                "Billing Cycle Remaining",
                "daysRemaining",
                "days",
            ),
        ]
    )

    return True


class CounterEntity(CoordinatorEntity, SensorEntity):
    """Representation of a Aussie Broadband counter metric sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        service_id: int,
        name: str,
        attribute: str,
        unit_of_measurement: str,
    ):
        """Initialize the sensor."""
        super(CounterEntity, self).__init__(coordinator)

        self._service_id = service_id
        self._name = name
        self._attribute = attribute
        self._unit_of_measurement = unit_of_measurement

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self.coordinator.data[self._attribute]

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return str(self._service_id) + ":" + self._attribute
