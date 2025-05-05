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

PRAYER_TIME_SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="Fajr",
        translation_key="prayer_fajr",
        icon="mdi:weather-sunset-up",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="shuruq",
        translation_key="prayer_shuruq",
        icon="mdi:weather-sunset",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Dhuhr",
        translation_key="prayer_dhuhr",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Asr",
        translation_key="prayer_asr",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Maghrib",
        translation_key="prayer_maghrib",
        icon="mdi:weather-sunset-down",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Isha",
        translation_key="prayer_isha",
        icon="mdi:weather-night",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Jumua",
        translation_key="prayer_jumua",
        icon="mdi:calendar-star",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Jumua 2",
        translation_key="prayer_jumua_2",
        icon="mdi:calendar-star",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

IQAMA_PRAYER_TIME_SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="Fajr_Iqama",
        translation_key="iqama_fajr",
        icon="mdi:weather-sunset-up",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Dhuhr_Iqama",
        translation_key="iqama_dhuhr",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Asr_Iqama",
        translation_key="iqama_asr",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Maghrib_Iqama",
        translation_key="iqama_maghrib",
        icon="mdi:weather-sunset-down",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Isha_Iqama",
        translation_key="iqama_isha",
        icon="mdi:weather-night",
        device_class=SensorDeviceClass.TIMESTAMP,
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
        return {
            k: v
            for k, v in self.coordinator.data.items()
            if k not in ["uid", "partner"]  # act as a filter
        }

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
        """Return the prayer time, ensuring correct timezone handling."""

        # Get prayer data from coordinator
        prayer_data = self.coordinator.data

        if not prayer_data:
            _LOGGER.warning(
                "No prayer data available yet for %s", self.entity_description.key
            )
            return None

        # Extract the required parameters
        calendar = prayer_data.get("calendar")
        timezone = prayer_data.get("timezone")

        if not calendar or not timezone:
            _LOGGER.warning(
                "Missing calendar or timezone data for %s",
                self.entity_description.key,
            )
            return None

        # Get today's date
        day = dt_util.now().date()

        # Extract the requested prayer time
        prayer_time = None
        prayer_name: str = ""
        if not isinstance(self.entity_description.key, str):
            raise TypeError(f"name must be a string for {self.entity_description.key}")
        prayer_name = self.entity_description.key
        try:
            if prayer_name.lower() == "shuruq":
                prayer_time = prayer_data.get("shuruq")
            elif prayer_name.lower() == "jumua":
                prayer_time = prayer_data.get("jumua")
                day = utils.get_next_friday()
            elif prayer_name.lower() == "jumua 2":
                prayer_time = prayer_data.get("jumua2")
                day = utils.get_next_friday()
            else:
                name = self.entity_description.key
                iqama_prayer_time = None

                if "iqama" in self.entity_description.key.lower():
                    name = self.entity_description.key.split("_")[0]
                    iqama_calendar = prayer_data.get("iqamaCalendar")
                    iqama_prayer_time = utils.extract_time_from_calendar(
                        iqama_calendar, name, day, timezone, mode_iqama=True
                    )
                prayer_time = utils.extract_time_from_calendar(
                    calendar, name, day, timezone
                )
                if "iqama" in self.entity_description.key.lower():
                    prayer_time = utils.add_minutes_to_time(
                        prayer_time, iqama_prayer_time
                    )  # here the prayer_time represent the iqama time

            localized_prayer_time = utils.time_with_timezone(timezone, day, prayer_time)
            if not localized_prayer_time:
                _LOGGER.warning(
                    "Could not determine prayer time for %s",
                    self.entity_description.key,
                )
                return None

            return localized_prayer_time.astimezone(dt_util.UTC)
        except KeyError as e:
            _LOGGER.error(
                "Key error retrieving prayer time for %s: %s",
                self.entity_description.key,
                e,
            )
            return None
        except ValueError as e:
            _LOGGER.error(
                "Value error retrieving prayer time for %s: %s",
                self.entity_description.key,
                e,
            )
            return None
        except TypeError as e:
            _LOGGER.error(
                "Type error retrieving prayer time for %s: %s",
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
