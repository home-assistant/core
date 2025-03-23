"""Provides a sensor for Home Connect."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
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

    appliance_types: tuple[str, ...] | None = None
    fetch_unit: bool = False


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
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        translation_key="freezer_door_alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_REFRIGERATOR,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        translation_key="refrigerator_door_alarm",
        appliance_types=("FridgeFreezer", "Refrigerator"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_TEMPERATURE_ALARM_FREEZER,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        translation_key="freezer_temperature_alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        translation_key="bean_container_empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_WATER_TANK_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        translation_key="water_tank_empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DRIP_TRAY_FULL,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        translation_key="drip_tray_full",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        translation_key="salt_nearly_empty",
        appliance_types=("Dishwasher",),
    ),
    HomeConnectSensorEntityDescription(
        key=EventKey.DISHCARE_DISHWASHER_EVENT_RINSE_AID_NEARLY_EMPTY,
        device_class=SensorDeviceClass.ENUM,
        options=EVENT_OPTIONS,
        translation_key="rinse_aid_nearly_empty",
        appliance_types=("Dishwasher",),
    ),
)


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return [
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


def _add_event_sensor_entity(
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    appliance: HomeConnectApplianceData,
    description: HomeConnectSensorEntityDescription,
    remove_listener: list[Callable[[], None]],
) -> None:
    """Add an event sensor entity."""
    if (
        (appliance_data := entry.runtime_data.data.get(appliance.info.ha_id)) is None
    ) or description.key not in appliance_data.events:
        return

    for listener in remove_listener:
        listener()
    async_add_entities(
        [
            HomeConnectEventSensor(entry.runtime_data, appliance, description),
        ]
    )


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

    for appliance in entry.runtime_data.data.values():
        for event_sensor_description in EVENT_SENSORS:
            if appliance.info.type not in cast(
                tuple[str, ...], event_sensor_description.appliance_types
            ):
                continue
            # We use a list as a kind of lazy initializer, as we can use the
            # remove_listener while we are initializing it.
            remove_listener_list: list[Callable[[], None]] = []
            remove_listener = entry.runtime_data.async_add_listener(
                partial(
                    _add_event_sensor_entity,
                    entry,
                    async_add_entities,
                    appliance,
                    event_sensor_description,
                    remove_listener_list,
                ),
                (appliance.info.ha_id, event_sensor_description.key),
            )
            remove_listener_list.append(remove_listener)
            entry.async_on_unload(remove_listener)


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
        event = self.appliance.events[cast(EventKey, self.bsh_key)]
        self._update_native_value(event.value)
