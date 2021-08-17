"""Support for Aussie Broadband metric sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN
from ...const import DATA_MEGABYTES
from ...core import HomeAssistant
from ..sensor import SensorEntity
from .const import CONF_SERVICE_ID

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up Aussie Broadband sensor from a config entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    service_id = entry.data[CONF_SERVICE_ID]

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
            CounterEntity(
                coordinator, service_id, "Total Usage", "usedMb", DATA_MEGABYTES
            ),
            CounterEntity(
                coordinator, service_id, "Downloaded", "downloadedMb", DATA_MEGABYTES
            ),
            CounterEntity(
                coordinator, service_id, "Uploaded", "uploadedMb", DATA_MEGABYTES
            ),
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
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_name = name
        self._attribute = attribute
        self._attr_unit_of_measurement = unit_of_measurement
        self._attr_unique_id = f"{service_id}:{attribute}"

    @property
    def state(self):
        """Return the state of the device."""
        return self.coordinator.data[self._attribute]
