"""Provides a sensor for Home Connect."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import cast

from aiohomeconnect.model import EventKey, StatusKey

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from .common import setup_home_connect_entry
from .const import (
    APPLIANCES_WITH_PROGRAMS,
    BSH_OPERATION_STATE_FINISHED,
    BSH_OPERATION_STATE_PAUSE,
    BSH_OPERATION_STATE_RUN,
    UNIT_MAP,
)
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity, constraint_fetcher

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

EVENT_OPTIONS = ["confirmed", "off", "present"]


@dataclass(frozen=True, kw_only=True)
class HomeConnectSensorEntityDescription(
    SensorEntityDescription,
):
    """Entity Description class for sensors."""

    default_value: str | None = None
    appliance_types: tuple[str, ...] | None = None
    fetch_unit: bool = False


BSH_PROGRAM_SENSORS = (
    HomeConnectSensorEntityDescription(
        key=EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="program_finish_time",
        appliance_types=(
            "CoffeeMaker",
            "CookProcessor",
            "Dishwasher",
            "Dryer",
            "Hood",
            "Oven",
            "Washer",
            "WasherDryer",
        ),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.BSH_COMMON_OPTION_PROGRAM_PROGRESS,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="program_progress",
        appliance_types=APPLIANCES_WITH_PROGRAMS,
    ),
)

SENSORS = (
    HomeConnectSensorEntityDescription(
        key=StatusKey.BSH_COMMON_OPERATION_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "inactive",
            "ready",
            "delayedstart",
            "run",
            "pause",
            "actionrequired",
            "finished",
            "error",
            "aborting",
        ],
        translation_key="operation_state",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.BSH_COMMON_DOOR_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "closed",
            "locked",
            "open",
        ],
        translation_key="door",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_COFFEE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="coffee_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_POWDER_COFFEE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="powder_coffee_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_HOT_WATER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_water_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_HOT_WATER_CUPS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_water_cups_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_HOT_MILK,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_FROTHY_MILK,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="frothy_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_MILK,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_COFFEE_AND_MILK,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="coffee_and_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_RISTRETTO_ESPRESSO,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="ristretto_espresso_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.BSH_COMMON_BATTERY_LEVEL,
        device_class=SensorDeviceClass.BATTERY,
        translation_key="battery_level",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.BSH_COMMON_VIDEO_CAMERA_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "disabled",
            "sleeping",
            "ready",
            "streaminglocal",
            "streamingcloud",
            "streaminglocalancloud",
            "error",
        ],
        translation_key="camera_state",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_LAST_SELECTED_MAP,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "tempmap",
            "map1",
            "map2",
            "map3",
        ],
        translation_key="last_selected_map",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.COOKING_OVEN_CURRENT_CAVITY_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="oven_current_cavity_temperature",
        fetch_unit=True,
    ),
)

EVENT_SENSORS = (
    HomeConnectSensorEntityDescription(
        key=EventKey.BSH_COMMON_EVENT_PROGRAM_ABORTED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="program_aborted",
        appliance_types=("Dishwasher", "CleaningRobot", "CookProcessor"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.BSH_COMMON_EVENT_PROGRAM_FINISHED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="program_finished",
        appliance_types=(
            "Oven",
            "Dishwasher",
            "Washer",
            "Dryer",
            "WasherDryer",
            "CleaningRobot",
            "CookProcessor",
        ),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.BSH_COMMON_EVENT_ALARM_CLOCK_ELAPSED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="alarm_clock_elapsed",
        appliance_types=("Oven", "Cooktop"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.COOKING_OVEN_EVENT_PREHEAT_FINISHED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="preheat_finished",
        appliance_types=("Oven", "Cooktop"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.COOKING_OVEN_EVENT_REGULAR_PREHEAT_FINISHED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="regular_preheat_finished",
        appliance_types=("Oven",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.LAUNDRY_CARE_DRYER_EVENT_DRYING_PROCESS_FINISHED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="drying_process_finished",
        appliance_types=("Dryer",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="salt_nearly_empty",
        appliance_types=("Dishwasher",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.DISHCARE_DISHWASHER_EVENT_RINSE_AID_NEARLY_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="rinse_aid_nearly_empty",
        appliance_types=("Dishwasher",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="bean_container_empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_WATER_TANK_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="water_tank_empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DRIP_TRAY_FULL,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="drip_tray_full",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_KEEP_MILK_TANK_COOL,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="keep_milk_tank_cool",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DESCALING_IN_20_CUPS,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="descaling_in_20_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DESCALING_IN_15_CUPS,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="descaling_in_15_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DESCALING_IN_10_CUPS,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="descaling_in_10_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DESCALING_IN_5_CUPS,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="descaling_in_5_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_SHOULD_BE_DESCALED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="device_should_be_descaled",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_DESCALING_OVERDUE,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="device_descaling_overdue",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_DESCALING_BLOCKAGE,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="device_descaling_blockage",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_SHOULD_BE_CLEANED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="device_should_be_cleaned",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_CLEANING_OVERDUE,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="device_cleaning_overdue",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_CALC_N_CLEAN_IN20CUPS,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="calc_n_clean_in20cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_CALC_N_CLEAN_IN15CUPS,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="calc_n_clean_in15cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_CALC_N_CLEAN_IN10CUPS,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="calc_n_clean_in10cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_CALC_N_CLEAN_IN5CUPS,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="calc_n_clean_in5cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_SHOULD_BE_CALC_N_CLEANED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="device_should_be_calc_n_cleaned",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_CALC_N_CLEAN_OVERDUE,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="device_calc_n_clean_overdue",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_CALC_N_CLEAN_BLOCKAGE,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="device_calc_n_clean_blockage",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="freezer_door_alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_REFRIGERATOR,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="refrigerator_door_alarm",
        appliance_types=("FridgeFreezer", "Refrigerator"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_TEMPERATURE_ALARM_FREEZER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="freezer_temperature_alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_EVENT_EMPTY_DUST_BOX_AND_CLEAN_FILTER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="empty_dust_box_and_clean_filter",
        appliance_types=("CleaningRobot",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_EVENT_ROBOT_IS_STUCK,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="robot_is_stuck",
        appliance_types=("CleaningRobot",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_EVENT_DOCKING_STATION_NOT_FOUND,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="docking_station_not_found",
        appliance_types=("CleaningRobot",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.LAUNDRY_CARE_WASHER_EVENT_I_DOS_1_FILL_LEVEL_POOR,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="poor_i_dos_1_fill_level",
        appliance_types=("Washer", "WasherDryer"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.LAUNDRY_CARE_WASHER_EVENT_I_DOS_2_FILL_LEVEL_POOR,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="poor_i_dos_2_fill_level",
        appliance_types=("Washer", "WasherDryer"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.COOKING_COMMON_EVENT_HOOD_GREASE_FILTER_MAX_SATURATION_NEARLY_REACHED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="grease_filter_max_saturation_nearly_reached",
        appliance_types=("Hood",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.COOKING_COMMON_EVENT_HOOD_GREASE_FILTER_MAX_SATURATION_REACHED,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        default_value="off",
        translation_key="grease_filter_max_saturation_reached",
        appliance_types=("Hood",),
    ),
)


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return [
        *[
            HomeConnectEventSensor(entry.runtime_data, appliance, description)
            for description in EVENT_SENSORS
            if description.appliance_types
            and appliance.info.type in description.appliance_types
        ],
        *[
            HomeConnectProgramSensor(entry.runtime_data, appliance, desc)
            for desc in BSH_PROGRAM_SENSORS
            if desc.appliance_types and appliance.info.type in desc.appliance_types
        ],
        *[
            HomeConnectSensor(entry.runtime_data, appliance, description)
            for description in SENSORS
            if description.key in appliance.status
        ],
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectSensor(HomeConnectEntity, SensorEntity):
    """Sensor class for Home Connect."""

    entity_description: HomeConnectSensorEntityDescription

    def update_native_value(self) -> None:
        """Set the value of the sensor."""
        status = self.appliance.status[cast(StatusKey, self.bsh_key)].value
        self._update_native_value(status)

    def _update_native_value(self, status: str | float) -> None:
        """Set the value of the sensor based on the given value."""
        match self.device_class:
            case SensorDeviceClass.TIMESTAMP:
                self._attr_native_value = dt_util.utcnow() + timedelta(
                    seconds=cast(float, status)
                )
            case SensorDeviceClass.ENUM:
                # Value comes back as an enum, we only really care about the
                # last part, so split it off
                # https://developer.home-connect.com/docs/status/operation_state
                self._attr_native_value = slugify(cast(str, status).split(".")[-1])
            case _:
                self._attr_native_value = status

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        if self.entity_description.fetch_unit:
            data = self.appliance.status[cast(StatusKey, self.bsh_key)]
            if data.unit:
                self._attr_native_unit_of_measurement = UNIT_MAP.get(
                    data.unit, data.unit
                )
            else:
                await self.fetch_unit()

    @constraint_fetcher
    async def fetch_unit(self) -> None:
        """Fetch the unit of measurement."""
        data = await self.coordinator.client.get_status_value(
            self.appliance.info.ha_id, status_key=cast(StatusKey, self.bsh_key)
        )
        if data.unit:
            self._attr_native_unit_of_measurement = UNIT_MAP.get(data.unit, data.unit)


class HomeConnectProgramSensor(HomeConnectSensor):
    """Sensor class for Home Connect sensors that reports information related to the running program."""

    program_running: bool = False

    async def async_added_to_hass(self) -> None:
        """Register listener."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                self._handle_operation_state_event,
                (self.appliance.info.ha_id, EventKey.BSH_COMMON_STATUS_OPERATION_STATE),
            )
        )

    @callback
    def _handle_operation_state_event(self) -> None:
        """Update status when an event for the entity is received."""
        self.program_running = (
            status := self.appliance.status.get(StatusKey.BSH_COMMON_OPERATION_STATE)
        ) is not None and status.value in [
            BSH_OPERATION_STATE_RUN,
            BSH_OPERATION_STATE_PAUSE,
            BSH_OPERATION_STATE_FINISHED,
        ]
        if not self.program_running:
            # reset the value when the program is not running, paused or finished
            self._attr_native_value = None
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return true if the sensor is available."""
        # These sensors are only available if the program is running, paused or finished.
        # Otherwise, some sensors report erroneous values.
        return super().available and self.program_running

    def update_native_value(self) -> None:
        """Update the program sensor's status."""
        self.program_running = (
            status := self.appliance.status.get(StatusKey.BSH_COMMON_OPERATION_STATE)
        ) is not None and status.value in [
            BSH_OPERATION_STATE_RUN,
            BSH_OPERATION_STATE_PAUSE,
            BSH_OPERATION_STATE_FINISHED,
        ]
        event = self.appliance.events.get(cast(EventKey, self.bsh_key))
        if event:
            self._update_native_value(event.value)


class HomeConnectEventSensor(HomeConnectSensor):
    """Sensor class for Home Connect events."""

    def update_native_value(self) -> None:
        """Update the sensor's status."""
        event = self.appliance.events.get(cast(EventKey, self.bsh_key))
        if event:
            self._update_native_value(event.value)
        elif not self._attr_native_value:
            self._attr_native_value = self.entity_description.default_value
