"""Binary sensor to indicate whether the current day is a school holiday."""

from __future__ import annotations

from datetime import date

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_COUNTRY, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SchoolHolidayConfigEntry
from .const import CONF_SENSOR_NAME, DOMAIN, LOGGER
from .coordinator import SchoolHolidayCoordinator
from .utils import get_device_name

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SchoolHolidayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the School Holiday binary sensor."""
    LOGGER.debug("Starting binary sensor setup")
    coordinator = entry.runtime_data
    country = str(entry.data.get(CONF_COUNTRY))
    region = str(entry.data.get(CONF_REGION))
    sensor_name = str(entry.data.get(CONF_SENSOR_NAME))

    async_add_entities(
        [
            SchoolHolidayBinarySensor(
                coordinator,
                sensor_name,
                country,
                region,
                entry.entry_id,
            )
        ],
        True,
    )


class SchoolHolidayBinarySensor(
    CoordinatorEntity[SchoolHolidayCoordinator], BinarySensorEntity
):
    """Representation of the School Holiday binary sensor."""

    _attr_icon = "mdi:school"

    def __init__(
        self,
        coordinator: SchoolHolidayCoordinator,
        sensor_name: str,
        country: str,
        region: str,
        entry_id: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_name = sensor_name
        self._country = country
        self._region = region
        self._attr_unique_id = f"{entry_id}_sensor"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            name=get_device_name(country, region),
        )

    @property
    def is_on(self) -> bool:
        """Return True if today is a school holiday."""
        today = date.today()
        events = self.coordinator.data or []
        return any(event["start"] <= today < event["end"] for event in events)
