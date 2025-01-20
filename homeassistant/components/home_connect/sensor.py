"""Provides a sensor for Home Connect."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import cast

from aiohomeconnect.model import Event, EventKey, StatusKey

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    APPLIANCES_WITH_PROGRAMS,
    BSH_OPERATION_STATE_FINISHED,
    BSH_OPERATION_STATE_PAUSE,
    BSH_OPERATION_STATE_RUN,
)
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


EVENT_OPTIONS = ["confirmed", "off", "present"]


@dataclass(frozen=True, kw_only=True)
class HomeConnectSensorEntityDescription(
    SensorEntityDescription,
):
    """Entity Description class for sensors."""

    default_value: str | None = None
    appliance_types: tuple[str, ...] | None = None


BSH_PROGRAM_SENSORS = (
    HomeConnectSensorEntityDescription(
        key=EventKey.BSH_COMMON_OPTION_REMAINING_PROGRAM_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="program_finish_time",
        appliance_types=(
            "CoffeMaker",
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
        key=EventKey.BSH_COMMON_OPTION_DURATION,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        appliance_types=("Oven",),
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
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="coffee_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_POWDER_COFFEE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="powder_coffee_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_HOT_WATER,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_water_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_HOT_WATER_CUPS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_water_cups_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_HOT_MILK,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="hot_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_FROTHY_MILK,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="frothy_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_MILK,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_COFFEE_AND_MILK,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="coffee_and_milk_counter",
    ),
    HomeConnectSensorEntityDescription(
        key=StatusKey.CONSUMER_PRODUCTS_COFFEE_MAKER_BEVERAGE_COUNTER_RISTRETTO_ESPRESSO,
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
)

EVENT_SENSORS = (
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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""

    async def get_entities_for_appliance(
        appliance: HomeConnectApplianceData,
    ) -> list[SensorEntity]:
        """Get a list of entities."""
        entities: list[SensorEntity] = []
        entities.extend(
            HomeConnectEventSensor(
                entry.runtime_data,
                appliance,
                description,
            )
            for description in EVENT_SENSORS
            if description.appliance_types
            and appliance.info.type in description.appliance_types
        )
        entities.extend(
            HomeConnectProgramSensor(entry.runtime_data, appliance, desc)
            for desc in BSH_PROGRAM_SENSORS
            if desc.appliance_types and appliance.info.type in desc.appliance_types
        )
        entities.extend(
            HomeConnectSensor(entry.runtime_data, appliance, description)
            for description in SENSORS
            if description.key in appliance.status
        )
        return entities

    entities = [
        entity
        for appliance in entry.runtime_data.data.values()
        for entity in await get_entities_for_appliance(appliance)
    ]
    async_add_entities(entities, True)


class HomeConnectSensor(HomeConnectEntity, SensorEntity):
    """Sensor class for Home Connect."""

    entity_description: HomeConnectSensorEntityDescription

    async def _async_event_update_listener(self, event: Event) -> None:
        """Update status when an event for the entity is received."""
        self.set_native_value(event.value)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the sensor's status."""
        self.set_native_value(self.appliance.status[StatusKey(self.bsh_key)].value)

    def set_native_value(self, status: str | float) -> None:
        """Set the value of the sensor."""
        match self.device_class:
            case SensorDeviceClass.TIMESTAMP:
                self._attr_native_value = dt_util.utcnow() + timedelta(
                    seconds=float(status)
                )
            case SensorDeviceClass.ENUM:
                # Value comes back as an enum, we only really care about the
                # last part, so split it off
                # https://developer.home-connect.com/docs/status/operation_state
                self._attr_native_value = slugify(cast(str, status).split(".")[-1])
            case _:
                self._attr_native_value = status
        _LOGGER.debug("Updated, new state: %s", self._attr_native_value)


class HomeConnectProgramSensor(HomeConnectSensor):
    """Sensor class for Home Connect sensors that reports information related to the running program."""

    program_running: bool = False

    async def async_added_to_hass(self) -> None:
        """Register listener."""
        await super().async_added_to_hass()
        self.coordinator.add_home_appliances_event_listener(
            self.appliance.info.ha_id,
            EventKey.BSH_COMMON_STATUS_OPERATION_STATE,
            self._async_event_update_operation_state_listener,
        )

    async def _async_event_update_operation_state_listener(self, _: Event) -> None:
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

    async def async_update(self) -> None:
        """Update the sensor's status."""
        # Program sensors value is not fetchable from the status endpoint,
        # so we can only wait for the event to update the value.


class HomeConnectEventSensor(HomeConnectSensor):
    """Sensor class for Home Connect events."""

    async def async_update(self) -> None:
        """Update the sensor's status."""
        if not self._attr_native_value:
            self._attr_native_value = self.entity_description.default_value
