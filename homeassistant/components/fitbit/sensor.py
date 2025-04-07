"""Support for the Fitbit API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging
from typing import Any, Final, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import FitbitApi
from .const import ATTRIBUTION, BATTERY_LEVELS, DOMAIN, FitbitScope, FitbitUnitSystem
from .coordinator import FitbitConfigEntry, FitbitDeviceCoordinator
from .exceptions import FitbitApiException, FitbitAuthException
from .model import FitbitDevice, config_from_entry_data

_LOGGER: Final = logging.getLogger(__name__)

_CONFIGURING: dict[str, str] = {}

SCAN_INTERVAL: Final = datetime.timedelta(minutes=30)

FITBIT_TRACKER_SUBSTRING = "/tracker/"


def _default_value_fn(result: dict[str, Any]) -> str:
    """Parse a Fitbit timeseries API responses."""
    return cast(str, result["value"])


def _distance_value_fn(result: dict[str, Any]) -> int | str:
    """Format function for distance values."""
    return format(float(_default_value_fn(result)), ".2f")


def _body_value_fn(result: dict[str, Any]) -> int | str:
    """Format function for body values."""
    return format(float(_default_value_fn(result)), ".1f")


def _clock_format_12h(result: dict[str, Any]) -> str:
    raw_state = result["value"]
    if raw_state == "":
        return "-"
    hours_str, minutes_str = raw_state.split(":")
    hours, minutes = int(hours_str), int(minutes_str)
    setting = "AM"
    if hours > 12:
        setting = "PM"
        hours -= 12
    elif hours == 0:
        hours = 12
    return f"{hours}:{minutes:02d} {setting}"


def _weight_unit(unit_system: FitbitUnitSystem) -> UnitOfMass:
    """Determine the weight unit."""
    if unit_system == FitbitUnitSystem.EN_US:
        return UnitOfMass.POUNDS
    if unit_system == FitbitUnitSystem.EN_GB:
        return UnitOfMass.STONES
    return UnitOfMass.KILOGRAMS


def _distance_unit(unit_system: FitbitUnitSystem) -> UnitOfLength:
    """Determine the distance unit."""
    if unit_system == FitbitUnitSystem.EN_US:
        return UnitOfLength.MILES
    return UnitOfLength.KILOMETERS


def _elevation_unit(unit_system: FitbitUnitSystem) -> UnitOfLength:
    """Determine the elevation unit."""
    if unit_system == FitbitUnitSystem.EN_US:
        return UnitOfLength.FEET
    return UnitOfLength.METERS


def _water_unit(unit_system: FitbitUnitSystem) -> UnitOfVolume:
    """Determine the water unit."""
    if unit_system == FitbitUnitSystem.EN_US:
        return UnitOfVolume.FLUID_OUNCES
    return UnitOfVolume.MILLILITERS


def _int_value_or_none(field: str) -> Callable[[dict[str, Any]], int | None]:
    """Value function that will parse the specified field if present."""

    def convert(result: dict[str, Any]) -> int | None:
        if (value := result["value"].get(field)) is not None:
            return int(value)
        return None

    return convert


@dataclass(frozen=True)
class FitbitSensorEntityDescription(SensorEntityDescription):
    """Describes Fitbit sensor entity."""

    unit_type: str | None = None
    value_fn: Callable[[dict[str, Any]], Any] = _default_value_fn
    unit_fn: Callable[[FitbitUnitSystem], str | None] = lambda x: None
    scope: FitbitScope | None = None

    @property
    def is_tracker(self) -> bool:
        """Return if the entity is a tracker."""
        return FITBIT_TRACKER_SUBSTRING in self.key


def _build_device_info(
    config_entry: FitbitConfigEntry, entity_description: FitbitSensorEntityDescription
) -> DeviceInfo:
    """Build device info for sensor entities info across devices."""
    unique_id = cast(str, config_entry.unique_id)
    if entity_description.is_tracker:
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{unique_id}_tracker")},
            translation_key="tracker",
            translation_placeholders={"display_name": config_entry.title},
        )
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, unique_id)},
    )


FITBIT_RESOURCES_LIST: Final[tuple[FitbitSensorEntityDescription, ...]] = (
    FitbitSensorEntityDescription(
        key="activities/activityCalories",
        translation_key="activity_calories",
        native_unit_of_measurement="cal",
        icon="mdi:fire",
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/calories",
        translation_key="calories",
        native_unit_of_measurement="cal",
        icon="mdi:fire",
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FitbitSensorEntityDescription(
        key="activities/caloriesBMR",
        translation_key="calories_bmr",
        native_unit_of_measurement="cal",
        icon="mdi:fire",
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/distance",
        icon="mdi:map-marker",
        device_class=SensorDeviceClass.DISTANCE,
        value_fn=_distance_value_fn,
        unit_fn=_distance_unit,
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FitbitSensorEntityDescription(
        key="activities/elevation",
        translation_key="elevation",
        icon="mdi:walk",
        device_class=SensorDeviceClass.DISTANCE,
        unit_fn=_elevation_unit,
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/floors",
        translation_key="floors",
        native_unit_of_measurement="floors",
        icon="mdi:walk",
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/heart",
        translation_key="resting_heart_rate",
        native_unit_of_measurement="bpm",
        icon="mdi:heart-pulse",
        value_fn=_int_value_or_none("restingHeartRate"),
        scope=FitbitScope.HEART_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FitbitSensorEntityDescription(
        key="activities/minutesFairlyActive",
        translation_key="minutes_fairly_active",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:walk",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/minutesLightlyActive",
        translation_key="minutes_lightly_active",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:walk",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/minutesSedentary",
        translation_key="minutes_sedentary",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:seat-recline-normal",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/minutesVeryActive",
        translation_key="minutes_very_active",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:run",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/steps",
        translation_key="steps",
        native_unit_of_measurement="steps",
        icon="mdi:walk",
        scope=FitbitScope.ACTIVITY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/activityCalories",
        translation_key="activity_calories",
        native_unit_of_measurement="cal",
        icon="mdi:fire",
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/calories",
        translation_key="calories",
        native_unit_of_measurement="cal",
        icon="mdi:fire",
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/distance",
        icon="mdi:map-marker",
        device_class=SensorDeviceClass.DISTANCE,
        value_fn=_distance_value_fn,
        unit_fn=_distance_unit,
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/elevation",
        translation_key="elevation",
        icon="mdi:walk",
        device_class=SensorDeviceClass.DISTANCE,
        unit_fn=_elevation_unit,
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/floors",
        translation_key="floors",
        native_unit_of_measurement="floors",
        icon="mdi:walk",
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/minutesFairlyActive",
        translation_key="minutes_fairly_active",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:walk",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/minutesLightlyActive",
        translation_key="minutes_lightly_active",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:walk",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/minutesSedentary",
        translation_key="minutes_sedentary",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:seat-recline-normal",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/minutesVeryActive",
        translation_key="minutes_very_active",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:run",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="activities/tracker/steps",
        translation_key="steps",
        native_unit_of_measurement="steps",
        icon="mdi:walk",
        scope=FitbitScope.ACTIVITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="body/bmi",
        translation_key="bmi",
        native_unit_of_measurement="BMI",
        icon="mdi:human",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_body_value_fn,
        scope=FitbitScope.WEIGHT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="body/fat",
        translation_key="body_fat",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:human",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_body_value_fn,
        scope=FitbitScope.WEIGHT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="body/weight",
        icon="mdi:human",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.WEIGHT,
        value_fn=_body_value_fn,
        unit_fn=_weight_unit,
        scope=FitbitScope.WEIGHT,
    ),
    FitbitSensorEntityDescription(
        key="sleep/awakeningsCount",
        translation_key="awakenings_count",
        native_unit_of_measurement="times awaken",
        icon="mdi:sleep",
        scope=FitbitScope.SLEEP,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="sleep/efficiency",
        translation_key="sleep_efficiency",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:sleep",
        state_class=SensorStateClass.MEASUREMENT,
        scope=FitbitScope.SLEEP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="sleep/minutesAfterWakeup",
        translation_key="minutes_after_wakeup",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.SLEEP,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="sleep/minutesAsleep",
        translation_key="sleep_minutes_asleep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.SLEEP,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="sleep/minutesAwake",
        translation_key="sleep_minutes_awake",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.SLEEP,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="sleep/minutesToFallAsleep",
        translation_key="sleep_minutes_to_fall_asleep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.SLEEP,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="sleep/timeInBed",
        translation_key="sleep_time_in_bed",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:hotel",
        device_class=SensorDeviceClass.DURATION,
        scope=FitbitScope.SLEEP,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="foods/log/caloriesIn",
        translation_key="calories_in",
        native_unit_of_measurement="cal",
        icon="mdi:food-apple",
        state_class=SensorStateClass.TOTAL_INCREASING,
        scope=FitbitScope.NUTRITION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FitbitSensorEntityDescription(
        key="foods/log/water",
        translation_key="water",
        icon="mdi:cup-water",
        unit_fn=_water_unit,
        state_class=SensorStateClass.TOTAL_INCREASING,
        scope=FitbitScope.NUTRITION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# Different description depending on clock format
SLEEP_START_TIME = FitbitSensorEntityDescription(
    key="sleep/startTime",
    translation_key="sleep_start_time",
    icon="mdi:clock",
    scope=FitbitScope.SLEEP,
    entity_category=EntityCategory.DIAGNOSTIC,
)
SLEEP_START_TIME_12HR = FitbitSensorEntityDescription(
    key="sleep/startTime",
    translation_key="sleep_start_time",
    icon="mdi:clock",
    value_fn=_clock_format_12h,
    scope=FitbitScope.SLEEP,
    entity_category=EntityCategory.DIAGNOSTIC,
)

FITBIT_RESOURCE_BATTERY = FitbitSensorEntityDescription(
    key="devices/battery",
    translation_key="battery",
    icon="mdi:battery",
    scope=FitbitScope.DEVICE,
    entity_category=EntityCategory.DIAGNOSTIC,
    has_entity_name=True,
)
FITBIT_RESOURCE_BATTERY_LEVEL = FitbitSensorEntityDescription(
    key="devices/battery_level",
    translation_key="battery_level",
    scope=FitbitScope.DEVICE,
    entity_category=EntityCategory.DIAGNOSTIC,
    has_entity_name=True,
    device_class=SensorDeviceClass.BATTERY,
    native_unit_of_measurement=PERCENTAGE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FitbitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fitbit sensor platform."""

    data = entry.runtime_data
    api = data.api

    # These are run serially to reuse the cached user profile, not gathered
    # to avoid two racing requests.
    user_profile = await api.async_get_user_profile()
    unit_system = await api.async_get_unit_system()

    fitbit_config = config_from_entry_data(entry.data)

    def is_explicit_enable(description: FitbitSensorEntityDescription) -> bool:
        """Determine if entity is enabled by default."""
        return fitbit_config.is_explicit_enable(description.key)

    def is_allowed_resource(description: FitbitSensorEntityDescription) -> bool:
        """Determine if an entity is allowed to be created."""
        return fitbit_config.is_allowed_resource(description.scope, description.key)

    resource_list = [
        *FITBIT_RESOURCES_LIST,
        SLEEP_START_TIME_12HR
        if fitbit_config.clock_format == "12H"
        else SLEEP_START_TIME,
    ]

    entities = [
        FitbitSensor(
            entry,
            api,
            user_profile.encoded_id,
            description,
            units=description.unit_fn(unit_system),
            enable_default_override=is_explicit_enable(description),
            device_info=_build_device_info(entry, description),
        )
        for description in resource_list
        if is_allowed_resource(description)
    ]
    async_add_entities(entities)

    if data.device_coordinator and is_allowed_resource(FITBIT_RESOURCE_BATTERY):
        battery_entities: list[SensorEntity] = [
            FitbitBatterySensor(
                data.device_coordinator,
                user_profile.encoded_id,
                FITBIT_RESOURCE_BATTERY,
                device=device,
                enable_default_override=is_explicit_enable(FITBIT_RESOURCE_BATTERY),
            )
            for device in data.device_coordinator.data.values()
        ]
        battery_entities.extend(
            FitbitBatteryLevelSensor(
                data.device_coordinator,
                user_profile.encoded_id,
                FITBIT_RESOURCE_BATTERY_LEVEL,
                device=device,
            )
            for device in data.device_coordinator.data.values()
        )
        async_add_entities(battery_entities)


class FitbitSensor(SensorEntity):
    """Implementation of a Fitbit sensor."""

    entity_description: FitbitSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: FitbitConfigEntry,
        api: FitbitApi,
        user_profile_id: str,
        description: FitbitSensorEntityDescription,
        units: str | None,
        enable_default_override: bool,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Fitbit sensor."""
        self.config_entry = config_entry
        self.entity_description = description
        self.api = api

        self._attr_unique_id = f"{user_profile_id}_{description.key}"
        self._attr_device_info = device_info

        if units is not None:
            self._attr_native_unit_of_measurement = units

        if enable_default_override:
            self._attr_entity_registry_enabled_default = True

    async def async_update(self) -> None:
        """Get the latest data from the Fitbit API and update the states."""
        try:
            result = await self.api.async_get_latest_time_series(
                self.entity_description.key
            )
        except FitbitAuthException:
            self._attr_available = False
            self.config_entry.async_start_reauth(self.hass)
        except FitbitApiException:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_native_value = self.entity_description.value_fn(result)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # We do not ask for an update with async_add_entities()
        # because it will update disabled entities.
        self.async_schedule_update_ha_state(force_refresh=True)


class FitbitBatterySensor(CoordinatorEntity[FitbitDeviceCoordinator], SensorEntity):
    """Implementation of a Fitbit battery sensor."""

    entity_description: FitbitSensorEntityDescription
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: FitbitDeviceCoordinator,
        user_profile_id: str,
        description: FitbitSensorEntityDescription,
        device: FitbitDevice,
        enable_default_override: bool,
    ) -> None:
        """Initialize the Fitbit sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device = device
        self._attr_unique_id = f"{user_profile_id}_{description.key}_{device.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{user_profile_id}_{device.id}")},
            name=device.device_version,
            model=device.device_version,
        )

        if enable_default_override:
            self._attr_entity_registry_enabled_default = True

    @property
    def icon(self) -> str | None:
        """Icon to use in the frontend, if any."""
        if battery_level := BATTERY_LEVELS.get(self.device.battery):
            return icon_for_battery_level(battery_level=battery_level)
        return self.entity_description.icon

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        return {
            "model": self.device.device_version,
            "type": self.device.type.lower() if self.device.type is not None else None,
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.device = self.coordinator.data[self.device.id]
        self._attr_native_value = self.device.battery
        self.async_write_ha_state()


class FitbitBatteryLevelSensor(
    CoordinatorEntity[FitbitDeviceCoordinator], SensorEntity
):
    """Implementation of a Fitbit battery level sensor."""

    entity_description: FitbitSensorEntityDescription
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: FitbitDeviceCoordinator,
        user_profile_id: str,
        description: FitbitSensorEntityDescription,
        device: FitbitDevice,
    ) -> None:
        """Initialize the Fitbit sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device = device
        self._attr_unique_id = f"{user_profile_id}_{description.key}_{device.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{user_profile_id}_{device.id}")},
            name=device.device_version,
            model=device.device_version,
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.device = self.coordinator.data[self.device.id]
        self._attr_native_value = self.device.battery_level
        self.async_write_ha_state()
