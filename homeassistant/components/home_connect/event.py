"""Event entities for Home Connect."""

from dataclasses import dataclass
from typing import cast

from aiohomeconnect.model import EventKey

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import (
    BSH_EVENT_PRESENT_STATE_CONFIRMED,
    BSH_EVENT_PRESENT_STATE_OFF,
    BSH_EVENT_PRESENT_STATE_PRESENT,
)
from .coordinator import HomeConnectApplianceCoordinator, HomeConnectConfigEntry
from .entity import HomeConnectEntity

PARALLEL_UPDATES = 0

EVENT_MAPPING = {
    BSH_EVENT_PRESENT_STATE_CONFIRMED: "confirmed",
    BSH_EVENT_PRESENT_STATE_OFF: "off",
    BSH_EVENT_PRESENT_STATE_PRESENT: "present",
}


@dataclass(frozen=True, kw_only=True)
class HomeConnectEventEntityDescription(
    EventEntityDescription,
):
    """Entity Description class for Events."""

    appliance_types: tuple[str, ...]


EVENTS = (
    HomeConnectEventEntityDescription(
        key=EventKey.BSH_COMMON_EVENT_PROGRAM_ABORTED,
        translation_key="program_aborted",
        appliance_types=("Dishwasher", "Microwave", "CleaningRobot", "CookProcessor"),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.BSH_COMMON_EVENT_PROGRAM_FINISHED,
        translation_key="program_finished",
        appliance_types=(
            "Oven",
            "Dishwasher",
            "Washer",
            "Dryer",
            "Microwave",
            "WasherDryer",
            "CleaningRobot",
            "CookProcessor",
        ),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.BSH_COMMON_EVENT_ALARM_CLOCK_ELAPSED,
        translation_key="alarm_clock_elapsed",
        appliance_types=("Oven", "Cooktop"),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.COOKING_OVEN_EVENT_PREHEAT_FINISHED,
        translation_key="preheat_finished",
        appliance_types=("Oven", "Cooktop"),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.COOKING_OVEN_EVENT_REGULAR_PREHEAT_FINISHED,
        translation_key="regular_preheat_finished",
        appliance_types=("Oven",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.LAUNDRY_CARE_DRYER_EVENT_DRYING_PROCESS_FINISHED,
        translation_key="drying_process_finished",
        appliance_types=("Dryer",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.DISHCARE_DISHWASHER_EVENT_SALT_NEARLY_EMPTY,
        translation_key="salt_nearly_empty",
        appliance_types=("Dishwasher",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.DISHCARE_DISHWASHER_EVENT_RINSE_AID_NEARLY_EMPTY,
        translation_key="rinse_aid_nearly_empty",
        appliance_types=("Dishwasher",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_BEAN_CONTAINER_EMPTY,
        translation_key="bean_container_empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_WATER_TANK_EMPTY,
        translation_key="water_tank_empty",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DRIP_TRAY_FULL,
        translation_key="drip_tray_full",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_KEEP_MILK_TANK_COOL,
        translation_key="keep_milk_tank_cool",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DESCALING_IN_20_CUPS,
        translation_key="descaling_in_20_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DESCALING_IN_15_CUPS,
        translation_key="descaling_in_15_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DESCALING_IN_10_CUPS,
        translation_key="descaling_in_10_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DESCALING_IN_5_CUPS,
        translation_key="descaling_in_5_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_SHOULD_BE_DESCALED,
        translation_key="device_should_be_descaled",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_DESCALING_OVERDUE,
        translation_key="device_descaling_overdue",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_DESCALING_BLOCKAGE,
        translation_key="device_descaling_blockage",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_SHOULD_BE_CLEANED,
        translation_key="device_should_be_cleaned",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_CLEANING_OVERDUE,
        translation_key="device_cleaning_overdue",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_CALC_N_CLEAN_IN20CUPS,
        translation_key="calc_n_clean_in_20_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_CALC_N_CLEAN_IN15CUPS,
        translation_key="calc_n_clean_in_15_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_CALC_N_CLEAN_IN10CUPS,
        translation_key="calc_n_clean_in_10_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_CALC_N_CLEAN_IN5CUPS,
        translation_key="calc_n_clean_in_5_cups",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_SHOULD_BE_CALC_N_CLEANED,
        translation_key="device_should_be_calc_n_cleaned",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_CALC_N_CLEAN_OVERDUE,
        translation_key="device_calc_n_clean_overdue",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_COFFEE_MAKER_EVENT_DEVICE_CALC_N_CLEAN_BLOCKAGE,
        translation_key="device_calc_n_clean_blockage",
        appliance_types=("CoffeeMaker",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_FREEZER,
        translation_key="freezer_door_alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_DOOR_ALARM_REFRIGERATOR,
        translation_key="refrigerator_door_alarm",
        appliance_types=("FridgeFreezer", "Refrigerator"),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.REFRIGERATION_FRIDGE_FREEZER_EVENT_TEMPERATURE_ALARM_FREEZER,
        translation_key="freezer_temperature_alarm",
        appliance_types=("FridgeFreezer", "Freezer"),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_EVENT_EMPTY_DUST_BOX_AND_CLEAN_FILTER,
        translation_key="empty_dust_box_and_clean_filter",
        appliance_types=("CleaningRobot",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_EVENT_ROBOT_IS_STUCK,
        translation_key="robot_is_stuck",
        appliance_types=("CleaningRobot",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.CONSUMER_PRODUCTS_CLEANING_ROBOT_EVENT_DOCKING_STATION_NOT_FOUND,
        translation_key="docking_station_not_found",
        appliance_types=("CleaningRobot",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.LAUNDRY_CARE_WASHER_EVENT_I_DOS_1_FILL_LEVEL_POOR,
        translation_key="poor_i_dos_1_fill_level",
        appliance_types=("Washer", "WasherDryer"),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.LAUNDRY_CARE_WASHER_EVENT_I_DOS_2_FILL_LEVEL_POOR,
        translation_key="poor_i_dos_2_fill_level",
        appliance_types=("Washer", "WasherDryer"),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.COOKING_COMMON_EVENT_HOOD_GREASE_FILTER_MAX_SATURATION_NEARLY_REACHED,
        translation_key="grease_filter_max_saturation_nearly_reached",
        appliance_types=("Hood",),
    ),
    HomeConnectEventEntityDescription(
        key=EventKey.COOKING_COMMON_EVENT_HOOD_GREASE_FILTER_MAX_SATURATION_REACHED,
        translation_key="grease_filter_max_saturation_reached",
        appliance_types=("Hood",),
    ),
)


def _get_entities_for_appliance(
    appliance_coordinator: HomeConnectApplianceCoordinator,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return [
        HomeConnectEventEntity(appliance_coordinator, description)
        for description in EVENTS
        if appliance_coordinator.data.info.type in description.appliance_types
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect event platform."""
    setup_home_connect_entry(
        hass,
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectEventEntity(HomeConnectEntity, EventEntity):
    """Event class for Home Connect events."""

    _attr_entity_registry_enabled_default = False
    _attr_event_types = list(EVENT_MAPPING.values())

    def update_native_value(self) -> None:
        """Set the value of the entity."""
        event = self.appliance.events.get(cast(EventKey, self.bsh_key))
        if event and (event_type := EVENT_MAPPING.get(cast(str, event.value))):
            self._trigger_event(event_type)
