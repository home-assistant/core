"""Module provides sensor entities for the Mawaqit integration in Home Assistant.

It includes the following sensor entities:
- Mosque information sensor
- Prayer time sensors
- Iqama prayer time sensors
- Next prayer sensors

The sensors are set up using the `async_setup_entry` function, which initializes the necessary coordinators and adds the entities to the platform.

Classes:
    MyMosqueSensor: Represents a mosque sensor.
    MawaqitPrayerTimeSensor: Represents a prayer time sensor.
    NextPrayerSensor: Represents the next prayer time and name sensor.

Functions:
        async_setup_entry: Sets up the Mawaqit sensor platform.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from . import utils
from .const import MOSQUES_COORDINATOR, PRAYER_NAMES, PRAYER_TIMES_COORDINATOR
from .coordinator import MosqueCoordinator, PrayerTimeCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

MOSQUE_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="mosque_info",
    translation_key="mosque_info",
    icon="mdi:mosque",
)


@dataclass(frozen=True, kw_only=True)
class MawaqitPrayerTimeSensorEntityDescription(SensorEntityDescription):
    """Describes Mawaqit prayer time sensor entity."""

    get_value: Callable[[dict], datetime | None]


PRAYER_TIME_SENSOR_DESCRIPTIONS = [
    MawaqitPrayerTimeSensorEntityDescription(
        key="Fajr",
        translation_key="prayer_fajr",
        icon="mdi:weather-sunset-up",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_regular_prayer_time(data, "Fajr"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="shuruq",
        translation_key="prayer_shuruq",
        icon="mdi:weather-sunset",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=utils.get_shuruq_time,
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Dhuhr",
        translation_key="prayer_dhuhr",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_regular_prayer_time(data, "Dhuhr"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Asr",
        translation_key="prayer_asr",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_regular_prayer_time(data, "Asr"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Maghrib",
        translation_key="prayer_maghrib",
        icon="mdi:weather-sunset-down",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_regular_prayer_time(data, "Maghrib"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Isha",
        translation_key="prayer_isha",
        icon="mdi:weather-night",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_regular_prayer_time(data, "Isha"),
    ),
]

JUMUA_PRAYER_TIME_SENSOR_DESCRIPTIONS = [
    MawaqitPrayerTimeSensorEntityDescription(
        key="Jumua",
        translation_key="prayer_jumua",
        icon="mdi:calendar-star",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_jumua_time(data, "jumua"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Jumua 2",
        translation_key="prayer_jumua_2",
        icon="mdi:calendar-star",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_jumua_time(data, "jumua2"),
    ),
]

IQAMA_PRAYER_TIME_SENSOR_DESCRIPTIONS = [
    MawaqitPrayerTimeSensorEntityDescription(
        key="Fajr_Iqama",
        translation_key="iqama_fajr",
        icon="mdi:weather-sunset-up",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_iqama_time(data, "Fajr"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Dhuhr_Iqama",
        translation_key="iqama_dhuhr",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_iqama_time(data, "Dhuhr"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Asr_Iqama",
        translation_key="iqama_asr",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_iqama_time(data, "Asr"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Maghrib_Iqama",
        translation_key="iqama_maghrib",
        icon="mdi:weather-sunset-down",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_iqama_time(data, "Maghrib"),
    ),
    MawaqitPrayerTimeSensorEntityDescription(
        key="Isha_Iqama",
        translation_key="iqama_isha",
        icon="mdi:weather-night",
        device_class=SensorDeviceClass.TIMESTAMP,
        get_value=lambda data: utils.get_iqama_time(data, "Isha"),
    ),
]

NEXT_SALAT_SENSOR_DESCRIPTION = [
    SensorEntityDescription(
        key="next_salat_name",
        translation_key="next_salat_name",
        icon="mdi:calendar-star",
    ),
    SensorEntityDescription(
        key="next_salat_time",
        translation_key="next_salat_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mawaqit sensor platform.

    This function is called by Home Assistant to set up the Mawaqit sensor platform.
    It initializes the mosque and prayer time coordinators and adds the necessary entities to the platform.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (ConfigEntry): The configuration entry for the Mawaqit sensor platform.
        async_add_entities (AddEntitiesCallback): A callback function to add entities to the platform.

    Returns:
        None

    """
    mosque_coordinator = config_entry.runtime_data.get(MOSQUES_COORDINATOR)
    prayer_time_coordinator = config_entry.runtime_data.get(PRAYER_TIMES_COORDINATOR)

    entities: list[SensorEntity] = []

    # Mosque Sensor
    entities.append(MyMosqueSensor(mosque_coordinator, "My mosque"))

    # Prayer Time Sensors
    entities.extend(
        [
            MawaqitPrayerTimeSensor(prayer_time_coordinator, desc)
            for desc in PRAYER_TIME_SENSOR_DESCRIPTIONS
        ]
    )

    # Register Jumua Prayer Time Sensors
    entities.extend(
        [
            MawaqitPrayerTimeSensor(prayer_time_coordinator, desc)
            for desc in JUMUA_PRAYER_TIME_SENSOR_DESCRIPTIONS
        ]
    )

    # Register Iqama Prayer Time Sensors
    entities.extend(
        [
            MawaqitPrayerTimeSensor(prayer_time_coordinator, desc)
            for desc in IQAMA_PRAYER_TIME_SENSOR_DESCRIPTIONS
        ]
    )

    # Register Next Prayer Sensors
    entities.extend(
        [
            NextPrayerSensor(prayer_time_coordinator, desc)
            for desc in NEXT_SALAT_SENSOR_DESCRIPTION
        ]
    )

    # Register the Sensors
    async_add_entities(new_entities=entities, update_before_add=True)

    _LOGGER.info("Mawaqit sensors successfully initialized")


class MyMosqueSensor(SensorEntity, CoordinatorEntity[MosqueCoordinator]):
    """Representation of a mosque sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, name: str) -> None:
        """Initialize the mosque sensor."""
        super().__init__(coordinator)
        self.entity_description = MOSQUE_SENSOR_DESCRIPTION
        self._attr_unique_id = f"mawaqit_mosque_{self.entity_description.key.lower()}"

        self.identifier = self._attr_unique_id

    @property
    def native_value(self) -> str | None:
        """Return the current mosque name as the sensor state."""
        return self.coordinator.data.get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes for the mosque sensor."""
        filtered_data = {}
        # Announcements are dynamic and could be useful for automations
        announcements = self.coordinator.data.get("announcements")
        if announcements:
            filtered_data["announcements"] = [
                f"{elem['title']} - {elem['content']}" for elem in announcements
            ]
        return filtered_data

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data is not None


class MawaqitPrayerTimeSensor(SensorEntity, CoordinatorEntity[PrayerTimeCoordinator]):
    """Representation of a prayer time sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, sensor_description) -> None:
        """Initialize the prayer time sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description
        self._attr_unique_id = f"mawaqit_{self.entity_description.key.lower()}"
        self.identifier = self._attr_unique_id

    @property
    def native_value(self) -> datetime | None:
        """Return the prayer time using the get_value function."""
        prayer_data = self.coordinator.data

        if not prayer_data:
            _LOGGER.warning(
                "No prayer data available yet for %s", self.entity_description.key
            )
            return None

        if (
            not hasattr(self.entity_description, "get_value")
            or self.entity_description.get_value is None
        ):
            _LOGGER.error(
                "No get_value function defined for %s", self.entity_description.key
            )
            return None

        try:
            return self.entity_description.get_value(prayer_data)
        except (KeyError, ValueError, TypeError) as e:
            _LOGGER.error(
                "Error retrieving prayer time for %s: %s",
                self.entity_description.key,
                e,
            )
            return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data is not None


class NextPrayerSensor(SensorEntity, CoordinatorEntity[PrayerTimeCoordinator]):
    """Sensor for the next prayer time and name."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        """Initialize the sensor with a specific description."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"next_prayer_{self.entity_description.key.lower()}"
        self.identifier = self._attr_unique_id
        self.next_prayer_index, self.time_next_prayer = self._get_next_prayer_info()

    @property
    def native_value(self) -> str | datetime | None:
        """Return the appropriate value based on the sensor type."""
        self.next_prayer_index, self.time_next_prayer = self._get_next_prayer_info()
        if self.entity_description.key == "next_salat_name":
            return PRAYER_NAMES[self.next_prayer_index]
        if self.entity_description.key == "next_salat_time":
            return self.time_next_prayer
        return None

    def _get_next_prayer_info(self):
        """Extract the next prayer info from the coordinator data."""
        prayer_calendar = self.coordinator.data.get("calendar")
        timezone = self.coordinator.data.get("timezone")
        current_time = dt_util.now()
        next_prayer_name, time_next_prayer = utils.find_next_prayer(
            current_time, prayer_calendar, timezone
        )
        return next_prayer_name, time_next_prayer

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data is not None
