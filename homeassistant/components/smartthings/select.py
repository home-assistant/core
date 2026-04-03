"""Support for select entities through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

LAMP_TO_HA = {
    "extraHigh": "extra_high",
    "high": "high",
    "mid": "mid",
    "low": "low",
    "on": "on",
    "off": "off",
}

SOUND_MODE_TO_HA = {
    "voice": "voice",
    "beep": "tone",
    "mute": "mute",
}

DRIVING_MODE_TO_HA = {
    "areaThenWalls": "area_then_walls",
    "wallFirst": "walls_first",
    "quickCleaningZigzagPattern": "quick_clean_zigzag_pattern",
}

CLEANING_TYPE_TO_HA = {
    "vacuum": "vacuum",
    "mop": "mop",
    "vacuumAndMopTogether": "vacuum_and_mop_together",
    "mopAfterVacuum": "mop_after_vacuum",
}

WASHER_SOIL_LEVEL_TO_HA = {
    "none": "none",
    "heavy": "heavy",
    "normal": "normal",
    "light": "light",
    "extraLight": "extra_light",
    "extraHeavy": "extra_heavy",
    "up": "up",
    "down": "down",
}

WATER_SPRAY_LEVEL_TO_HA = {
    "high": "high",
    "mediumHigh": "moderate_high",
    "medium": "medium",
    "mediumLow": "moderate_low",
    "low": "low",
}

WASHER_SPIN_LEVEL_TO_HA = {
    "none": "none",
    "rinseHold": "rinse_hold",
    "noSpin": "no_spin",
    "low": "low",
    "extraLow": "extra_low",
    "delicate": "delicate",
    "medium": "medium",
    "high": "high",
    "extraHigh": "extra_high",
    "200": "200",
    "400": "400",
    "600": "600",
    "800": "800",
    "1000": "1000",
    "1200": "1200",
    "1400": "1400",
    "1600": "1600",
}

WASHER_WATER_TEMPERATURE_TO_HA = {
    "none": "none",
    "20": "20",
    "30": "30",
    "40": "40",
    "50": "50",
    "60": "60",
    "65": "65",
    "70": "70",
    "75": "75",
    "80": "80",
    "90": "90",
    "95": "95",
    "tapCold": "tap_cold",
    "cold": "cold",
    "cool": "cool",
    "ecoWarm": "eco_warm",
    "warm": "warm",
    "semiHot": "semi_hot",
    "hot": "hot",
    "extraHot": "extra_hot",
    "extraLow": "extra_low",
    "low": "low",
    "mediumLow": "medium_low",
    "medium": "medium",
    "high": "high",
}


@dataclass(frozen=True, kw_only=True)
class SmartThingsSelectDescription(SelectEntityDescription):
    """Class describing SmartThings select entities."""

    key: Capability
    requires_remote_control_status: bool = False
    options_attribute: Attribute
    status_attribute: Attribute
    command: Command
    options_map: dict[str, str] | None = None
    default_options: list[str] | None = None
    extra_components: list[str] | None = None
    capability_ignore_list: list[Capability] | None = None
    value_is_integer: bool = False


CAPABILITIES_TO_SELECT: dict[Capability | str, SmartThingsSelectDescription] = {
    Capability.DISHWASHER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.DISHWASHER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
    ),
    Capability.DRYER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.DRYER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
        default_options=["run", "pause", "stop"],
    ),
    Capability.WASHER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.WASHER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
        default_options=["run", "pause", "stop"],
    ),
    Capability.SAMSUNG_CE_AUTO_DISPENSE_DETERGENT: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_AUTO_DISPENSE_DETERGENT,
        translation_key="detergent_amount",
        options_attribute=Attribute.SUPPORTED_AMOUNT,
        status_attribute=Attribute.AMOUNT,
        command=Command.SET_AMOUNT,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_FLEXIBLE_AUTO_DISPENSE_DETERGENT: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_FLEXIBLE_AUTO_DISPENSE_DETERGENT,
        translation_key="flexible_detergent_amount",
        options_attribute=Attribute.SUPPORTED_AMOUNT,
        status_attribute=Attribute.AMOUNT,
        command=Command.SET_AMOUNT,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_LAMP: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_LAMP,
        translation_key="lamp",
        options_attribute=Attribute.SUPPORTED_BRIGHTNESS_LEVEL,
        status_attribute=Attribute.BRIGHTNESS_LEVEL,
        command=Command.SET_BRIGHTNESS_LEVEL,
        options_map=LAMP_TO_HA,
        entity_category=EntityCategory.CONFIG,
        extra_components=["hood"],
        capability_ignore_list=[Capability.SAMSUNG_CE_CONNECTION_STATE],
    ),
    Capability.SAMSUNG_CE_SOUND_DETECTION_SENSITIVITY: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_SOUND_DETECTION_SENSITIVITY,
        translation_key="sound_detection_sensitivity",
        options_attribute=Attribute.SUPPORTED_LEVELS,
        status_attribute=Attribute.LEVEL,
        command=Command.SET_LEVEL,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    Capability.CUSTOM_WASHER_SPIN_LEVEL: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_SPIN_LEVEL,
        translation_key="spin_level",
        options_attribute=Attribute.SUPPORTED_WASHER_SPIN_LEVEL,
        status_attribute=Attribute.WASHER_SPIN_LEVEL,
        command=Command.SET_WASHER_SPIN_LEVEL,
        options_map=WASHER_SPIN_LEVEL_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.CUSTOM_WASHER_SOIL_LEVEL: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_SOIL_LEVEL,
        translation_key="soil_level",
        options_attribute=Attribute.SUPPORTED_WASHER_SOIL_LEVEL,
        status_attribute=Attribute.WASHER_SOIL_LEVEL,
        command=Command.SET_WASHER_SOIL_LEVEL,
        options_map=WASHER_SOIL_LEVEL_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.CUSTOM_WASHER_WATER_TEMPERATURE: SmartThingsSelectDescription(
        key=Capability.CUSTOM_WASHER_WATER_TEMPERATURE,
        translation_key="water_temperature",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_WASHER_WATER_TEMPERATURE,
        status_attribute=Attribute.WASHER_WATER_TEMPERATURE,
        command=Command.SET_WASHER_WATER_TEMPERATURE,
        options_map=WASHER_WATER_TEMPERATURE_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_ROBOT_CLEANER_WATER_SPRAY_LEVEL: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_ROBOT_CLEANER_WATER_SPRAY_LEVEL,
        translation_key="robot_cleaner_water_spray_level",
        options_attribute=Attribute.SUPPORTED_WATER_SPRAY_LEVELS,
        status_attribute=Attribute.WATER_SPRAY_LEVEL,
        command=Command.SET_WATER_SPRAY_LEVEL,
        options_map=WATER_SPRAY_LEVEL_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_ROBOT_CLEANER_DRIVING_MODE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_ROBOT_CLEANER_DRIVING_MODE,
        translation_key="robot_cleaner_driving_mode",
        options_attribute=Attribute.SUPPORTED_DRIVING_MODES,
        status_attribute=Attribute.DRIVING_MODE,
        command=Command.SET_DRIVING_MODE,
        options_map=DRIVING_MODE_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_DUST_FILTER_ALARM: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DUST_FILTER_ALARM,
        translation_key="dust_filter_alarm",
        options_attribute=Attribute.SUPPORTED_ALARM_THRESHOLDS,
        status_attribute=Attribute.ALARM_THRESHOLD,
        command=Command.SET_ALARM_THRESHOLD,
        entity_category=EntityCategory.CONFIG,
        value_is_integer=True,
    ),
    Capability.SAMSUNG_CE_ROBOT_CLEANER_SYSTEM_SOUND_MODE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_ROBOT_CLEANER_SYSTEM_SOUND_MODE,
        translation_key="robot_cleaner_sound_mode",
        options_attribute=Attribute.SUPPORTED_SOUND_MODES,
        status_attribute=Attribute.SOUND_MODE,
        command=Command.SET_SOUND_MODE,
        options_map=SOUND_MODE_TO_HA,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    Capability.SAMSUNG_CE_ROBOT_CLEANER_CLEANING_TYPE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_ROBOT_CLEANER_CLEANING_TYPE,
        translation_key="robot_cleaner_cleaning_type",
        options_attribute=Attribute.SUPPORTED_CLEANING_TYPES,
        status_attribute=Attribute.CLEANING_TYPE,
        command=Command.SET_CLEANING_TYPE,
        options_map=CLEANING_TYPE_TO_HA,
        entity_category=EntityCategory.CONFIG,
    ),
}
DISHWASHER_WASHING_OPTIONS_TO_SELECT: dict[
    Attribute | str, SmartThingsSelectDescription
] = {
    Attribute.SELECTED_ZONE: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS,
        translation_key="selected_zone",
        options_attribute=Attribute.SELECTED_ZONE,
        status_attribute=Attribute.SELECTED_ZONE,
        command=Command.SET_SELECTED_ZONE,
        entity_category=EntityCategory.CONFIG,
        requires_remote_control_status=True,
    ),
    Attribute.ZONE_BOOSTER: SmartThingsSelectDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS,
        translation_key="zone_booster",
        options_attribute=Attribute.ZONE_BOOSTER,
        status_attribute=Attribute.ZONE_BOOSTER,
        command=Command.SET_ZONE_BOOSTER,
        entity_category=EntityCategory.CONFIG,
        requires_remote_control_status=True,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add select entities for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsSelectEntity(entry_data.client, device, description, component)
        for capability, description in CAPABILITIES_TO_SELECT.items()
        for device in entry_data.devices.values()
        for component in device.status
        if capability in device.status[component]
        and (
            component == MAIN
            or (
                description.extra_components is not None
                and component in description.extra_components
            )
        )
        and (
            description.capability_ignore_list is None
            or any(
                capability not in device.status[component]
                for capability in description.capability_ignore_list
            )
        )
    )
    async_add_entities(
        SmartThingsDishwasherWashingOptionSelectEntity(
            entry_data.client,
            device,
            DISHWASHER_WASHING_OPTIONS_TO_SELECT[attribute],
        )
        for device in entry_data.devices.values()
        for component in device.status
        if component == MAIN
        and Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS in device.status[component]
        for attribute in cast(
            list[str],
            device.status[component][Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS][
                Attribute.SUPPORTED_LIST
            ].value,
        )
        if attribute in DISHWASHER_WASHING_OPTIONS_TO_SELECT
    )


class SmartThingsSelectEntity(SmartThingsEntity, SelectEntity):
    """Define a SmartThings select."""

    entity_description: SmartThingsSelectDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSelectDescription,
        component: str,
        extra_capabilities: set[Capability] | None = None,
    ) -> None:
        """Initialize the instance."""
        capabilities = {entity_description.key}
        if entity_description.requires_remote_control_status:
            capabilities.add(Capability.REMOTE_CONTROL_STATUS)
        if extra_capabilities is not None:
            capabilities.update(extra_capabilities)
        super().__init__(client, device, capabilities, component=component)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.device.device_id}_{component}_{entity_description.key}_{entity_description.status_attribute}_{entity_description.status_attribute}"

    @property
    def options(self) -> list[str]:
        """Return the list of options."""
        options: list[str] = (
            self.get_attribute_value(
                self.entity_description.key, self.entity_description.options_attribute
            )
            or self.entity_description.default_options
            or []
        )
        if self.entity_description.options_map:
            options = [
                self.entity_description.options_map.get(option, option)
                for option in options
            ]
        if self.entity_description.value_is_integer:
            options = [str(option) for option in options]
        return options

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        option = self.get_attribute_value(
            self.entity_description.key, self.entity_description.status_attribute
        )
        if self.entity_description.options_map:
            option = self.entity_description.options_map.get(option)
        if self.entity_description.value_is_integer and option is not None:
            option = str(option)
        return option

    def _validate_before_select(self) -> None:
        """Validate that the select can be used."""
        if (
            self.entity_description.requires_remote_control_status
            and self.get_attribute_value(
                Capability.REMOTE_CONTROL_STATUS, Attribute.REMOTE_CONTROL_ENABLED
            )
            == "false"
        ):
            raise ServiceValidationError(
                "Can only be updated when remote control is enabled"
            )

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._validate_before_select()
        new_option: str | int = option
        if self.entity_description.options_map:
            new_option = next(
                (
                    key
                    for key, value in self.entity_description.options_map.items()
                    if value == option
                ),
                new_option,
            )
        if self.entity_description.value_is_integer:
            new_option = int(option)
        await self.execute_device_command(
            self.entity_description.key,
            self.entity_description.command,
            new_option,
        )


class SmartThingsDishwasherWashingOptionSelectEntity(SmartThingsSelectEntity):
    """Define a SmartThings select for a dishwasher washing option."""

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSelectDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            client,
            device,
            entity_description,
            MAIN,
            {
                Capability.DISHWASHER_OPERATING_STATE,
                Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
                Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
                Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE_DETAILS,
            },
        )

    @property
    def options(self) -> list[str]:
        """Return the list of options."""
        device_options = self.get_attribute_value(
            self.entity_description.key, self.entity_description.options_attribute
        )["settable"]
        selected_course = self.get_attribute_value(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE, Attribute.WASHING_COURSE
        )
        course_details = self.get_attribute_value(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE_DETAILS,
            Attribute.PREDEFINED_COURSES,
        )
        course_options = set(
            next(
                (
                    detail["options"][self.entity_description.options_attribute][
                        "settable"
                    ]
                    for detail in course_details
                    if detail["courseName"] == selected_course
                ),
                [],
            )
        )
        return [option for option in device_options if option in course_options]

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.get_attribute_value(
            self.entity_description.key, self.entity_description.status_attribute
        )["value"]

    def _validate_before_select(self) -> None:
        """Validate that the select can be used."""
        super()._validate_before_select()
        if (
            self.get_attribute_value(
                Capability.DISHWASHER_OPERATING_STATE, Attribute.MACHINE_STATE
            )
            != "stop"
        ):
            raise ServiceValidationError(
                "Can only be updated when dishwasher machine state is stop"
            )

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._validate_before_select()
        selected_course = self.get_attribute_value(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE, Attribute.WASHING_COURSE
        )
        options = {
            option: self.get_attribute_value(self.entity_description.key, option)[
                "value"
            ]
            for option in self.get_attribute_value(
                self.entity_description.key, Attribute.SUPPORTED_LIST
            )
        }
        options[self.entity_description.options_attribute] = option
        await self.execute_device_command(
            Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
            Command.CANCEL,
            False,
        )
        await self.execute_device_command(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
            Command.SET_WASHING_COURSE,
            selected_course,
        )
        await self.execute_device_command(
            self.entity_description.key,
            Command.SET_OPTIONS,
            options,
        )
