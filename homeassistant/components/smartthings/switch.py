"""Support for switches through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import INVALID_SWITCH_CATEGORIES, MAIN
from .entity import SmartThingsEntity
from .util import deprecate_entity

CAPABILITIES = (
    Capability.SWITCH_LEVEL,
    Capability.COLOR_CONTROL,
    Capability.COLOR_TEMPERATURE,
    Capability.FAN_SPEED,
)

AC_CAPABILITIES = (
    Capability.AIR_CONDITIONER_MODE,
    Capability.AIR_CONDITIONER_FAN_MODE,
    Capability.TEMPERATURE_MEASUREMENT,
    Capability.THERMOSTAT_COOLING_SETPOINT,
)

MEDIA_PLAYER_CAPABILITIES = (
    Capability.AUDIO_MUTE,
    Capability.AUDIO_VOLUME,
)


@dataclass(frozen=True, kw_only=True)
class SmartThingsSwitchEntityDescription(SwitchEntityDescription):
    """Describe a SmartThings switch entity."""

    status_attribute: Attribute
    component_translation_key: dict[str, str] | None = None
    on_key: str | bool = "on"
    on_command: Command = Command.ON
    off_command: Command = Command.OFF


@dataclass(frozen=True, kw_only=True)
class SmartThingsCommandSwitchEntityDescription(SmartThingsSwitchEntityDescription):
    """Describe a SmartThings switch entity."""

    command: Command
    off_key: str | bool = "off"


@dataclass(frozen=True, kw_only=True)
class SmartThingsDishwasherWashingOptionSwitchEntityDescription(
    SmartThingsCommandSwitchEntityDescription
):
    """Describe a SmartThings switch entity for a dishwasher washing option."""

    on_key: str | bool = True
    off_key: str | bool = False


SWITCH = SmartThingsSwitchEntityDescription(
    key=Capability.SWITCH,
    status_attribute=Attribute.SWITCH,
    name=None,
)
CAPABILITY_TO_COMMAND_SWITCHES: dict[
    Capability | str, SmartThingsCommandSwitchEntityDescription
] = {
    Capability.SAMSUNG_CE_AIR_CONDITIONER_LIGHTING: SmartThingsCommandSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_AIR_CONDITIONER_LIGHTING,
        translation_key="display_lighting",
        status_attribute=Attribute.LIGHTING,
        command=Command.SET_LIGHTING_LEVEL,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.CUSTOM_DRYER_WRINKLE_PREVENT: SmartThingsCommandSwitchEntityDescription(
        key=Capability.CUSTOM_DRYER_WRINKLE_PREVENT,
        translation_key="wrinkle_prevent",
        status_attribute=Attribute.DRYER_WRINKLE_PREVENT,
        command=Command.SET_DRYER_WRINKLE_PREVENT,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_STEAM_CLOSET_AUTO_CYCLE_LINK: SmartThingsCommandSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_STEAM_CLOSET_AUTO_CYCLE_LINK,
        translation_key="auto_cycle_link",
        status_attribute=Attribute.STEAM_CLOSET_AUTO_CYCLE_LINK,
        command=Command.SET_STEAM_CLOSET_AUTO_CYCLE_LINK,
        entity_category=EntityCategory.CONFIG,
    ),
}
CAPABILITY_TO_SWITCHES: dict[Capability | str, SmartThingsSwitchEntityDescription] = {
    Capability.SAMSUNG_CE_AIR_CONDITIONER_BEEP: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_AIR_CONDITIONER_BEEP,
        translation_key="sound_effect",
        status_attribute=Attribute.BEEP,
        on_key="on",
        on_command=Command.ON,
        off_command=Command.OFF,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_WASHER_BUBBLE_SOAK: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_WASHER_BUBBLE_SOAK,
        translation_key="bubble_soak",
        status_attribute=Attribute.STATUS,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SWITCH: SmartThingsSwitchEntityDescription(
        key=Capability.SWITCH,
        status_attribute=Attribute.SWITCH,
        component_translation_key={
            "icemaker": "ice_maker",
            "icemaker-02": "ice_maker_2",
        },
    ),
    Capability.SAMSUNG_CE_SABBATH_MODE: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_SABBATH_MODE,
        translation_key="sabbath_mode",
        status_attribute=Attribute.STATUS,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_POWER_COOL: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_POWER_COOL,
        translation_key="power_cool",
        status_attribute=Attribute.ACTIVATED,
        on_key="True",
        on_command=Command.ACTIVATE,
        off_command=Command.DEACTIVATE,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_POWER_FREEZE: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_POWER_FREEZE,
        translation_key="power_freeze",
        status_attribute=Attribute.ACTIVATED,
        on_key="True",
        on_command=Command.ACTIVATE,
        off_command=Command.DEACTIVATE,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_STEAM_CLOSET_SANITIZE_MODE: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_STEAM_CLOSET_SANITIZE_MODE,
        translation_key="sanitize",
        status_attribute=Attribute.STATUS,
        entity_category=EntityCategory.CONFIG,
    ),
    Capability.SAMSUNG_CE_STEAM_CLOSET_KEEP_FRESH_MODE: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_STEAM_CLOSET_KEEP_FRESH_MODE,
        translation_key="keep_fresh_mode",
        status_attribute=Attribute.STATUS,
        entity_category=EntityCategory.CONFIG,
    ),
}
DISHWASHER_WASHING_OPTIONS_TO_SWITCHES: dict[
    Attribute | str, SmartThingsDishwasherWashingOptionSwitchEntityDescription
] = {
    Attribute.ADD_RINSE: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.ADD_RINSE,
        translation_key="add_rinse",
        status_attribute=Attribute.ADD_RINSE,
        command=Command.SET_ADD_RINSE,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.DRY_PLUS: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.DRY_PLUS,
        translation_key="dry_plus",
        status_attribute=Attribute.DRY_PLUS,
        command=Command.SET_DRY_PLUS,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.HEATED_DRY: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.HEATED_DRY,
        translation_key="heated_dry",
        status_attribute=Attribute.HEATED_DRY,
        command=Command.SET_HEATED_DRY,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.HIGH_TEMP_WASH: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.HIGH_TEMP_WASH,
        translation_key="high_temp_wash",
        status_attribute=Attribute.HIGH_TEMP_WASH,
        command=Command.SET_HIGH_TEMP_WASH,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.HOT_AIR_DRY: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.HOT_AIR_DRY,
        translation_key="hot_air_dry",
        status_attribute=Attribute.HOT_AIR_DRY,
        command=Command.SET_HOT_AIR_DRY,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.MULTI_TAB: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.MULTI_TAB,
        translation_key="multi_tab",
        status_attribute=Attribute.MULTI_TAB,
        command=Command.SET_MULTI_TAB,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.RINSE_PLUS: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.RINSE_PLUS,
        translation_key="rinse_plus",
        status_attribute=Attribute.RINSE_PLUS,
        command=Command.SET_RINSE_PLUS,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.SANITIZE: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.SANITIZE,
        translation_key="sanitize",
        status_attribute=Attribute.SANITIZE,
        command=Command.SET_SANITIZE,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.SANITIZING_WASH: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.SANITIZING_WASH,
        translation_key="sanitizing_wash",
        status_attribute=Attribute.SANITIZING_WASH,
        command=Command.SET_SANITIZING_WASH,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.SPEED_BOOSTER: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.SPEED_BOOSTER,
        translation_key="speed_booster",
        status_attribute=Attribute.SPEED_BOOSTER,
        command=Command.SET_SPEED_BOOSTER,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.STEAM_SOAK: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.STEAM_SOAK,
        translation_key="steam_soak",
        status_attribute=Attribute.STEAM_SOAK,
        command=Command.SET_STEAM_SOAK,
        entity_category=EntityCategory.CONFIG,
    ),
    Attribute.STORM_WASH: SmartThingsDishwasherWashingOptionSwitchEntityDescription(
        key=Attribute.STORM_WASH,
        translation_key="storm_wash",
        status_attribute=Attribute.STORM_WASH,
        command=Command.SET_STORM_WASH,
        entity_category=EntityCategory.CONFIG,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add switches for a config entry."""
    entry_data = entry.runtime_data
    entities: list[SmartThingsEntity] = [
        SmartThingsCommandSwitch(
            entry_data.client,
            device,
            description,
            Capability(capability),
        )
        for device in entry_data.devices.values()
        for capability, description in CAPABILITY_TO_COMMAND_SWITCHES.items()
        if capability in device.status[MAIN]
    ]
    entities.extend(
        SmartThingsSwitch(
            entry_data.client,
            device,
            description,
            Capability(capability),
            component,
        )
        for device in entry_data.devices.values()
        for capability, description in CAPABILITY_TO_SWITCHES.items()
        for component in device.status
        if capability in device.status[component]
        and (
            (description.component_translation_key is None and component == MAIN)
            or (
                description.component_translation_key is not None
                and component in description.component_translation_key
            )
        )
    )
    entities.extend(
        SmartThingsDishwasherWashingOptionSwitch(
            entry_data.client,
            device,
            DISHWASHER_WASHING_OPTIONS_TO_SWITCHES[attribute],
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
        if attribute in DISHWASHER_WASHING_OPTIONS_TO_SWITCHES
    )
    entity_registry = er.async_get(hass)
    for device in entry_data.devices.values():
        if (
            Capability.SWITCH in device.status[MAIN]
            and not any(
                capability in device.status[MAIN] for capability in CAPABILITIES
            )
            and not all(
                capability in device.status[MAIN] for capability in AC_CAPABILITIES
            )
        ):
            media_player = all(
                capability in device.status[MAIN]
                for capability in MEDIA_PLAYER_CAPABILITIES
            )
            appliance = (
                device.device.components[MAIN].manufacturer_category
                in INVALID_SWITCH_CATEGORIES
            )
            dhw = Capability.SAMSUNG_CE_EHS_FSV_SETTINGS in device.status[MAIN]
            if media_player or appliance or dhw:
                if appliance:
                    issue = "appliance"
                    version = "2025.10.0"
                elif media_player:
                    issue = "media_player"
                    version = "2025.10.0"
                else:
                    issue = "dhw"
                    version = "2025.12.0"
                if deprecate_entity(
                    hass,
                    entity_registry,
                    SWITCH_DOMAIN,
                    f"{device.device.device_id}_{MAIN}_{Capability.SWITCH}_{Attribute.SWITCH}_{Attribute.SWITCH}",
                    f"deprecated_switch_{issue}",
                    version,
                ):
                    entities.append(
                        SmartThingsSwitch(
                            entry_data.client,
                            device,
                            SWITCH,
                            Capability.SWITCH,
                        )
                    )
                continue
            entities.append(
                SmartThingsSwitch(
                    entry_data.client,
                    device,
                    SWITCH,
                    Capability.SWITCH,
                )
            )
    async_add_entities(entities)


class SmartThingsSwitch(SmartThingsEntity, SwitchEntity):
    """Define a SmartThings switch."""

    entity_description: SmartThingsSwitchEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSwitchEntityDescription,
        capability: Capability,
        component: str = MAIN,
        extra_capabilities: set[Capability] | None = None,
    ) -> None:
        """Initialize the switch."""
        extra_capabilities = set() if extra_capabilities is None else extra_capabilities
        super().__init__(
            client, device, {capability} | extra_capabilities, component=component
        )
        self.entity_description = entity_description
        self.switch_capability = capability
        self._attr_unique_id = f"{device.device.device_id}_{component}_{capability}_{entity_description.status_attribute}_{entity_description.status_attribute}"
        if (
            translation_keys := entity_description.component_translation_key
        ) is not None and (
            translation_key := translation_keys.get(component)
        ) is not None:
            self._attr_translation_key = translation_key

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.off_command,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.on_command,
        )

    def _current_state(self) -> Any:
        return self.get_attribute_value(
            self.switch_capability, self.entity_description.status_attribute
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._current_state() == self.entity_description.on_key


class SmartThingsCommandSwitch(SmartThingsSwitch):
    """Define a SmartThings command switch."""

    entity_description: SmartThingsCommandSwitchEntityDescription

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.command,
            self.entity_description.off_key,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.command,
            self.entity_description.on_key,
        )


class SmartThingsDishwasherWashingOptionSwitch(SmartThingsCommandSwitch):
    """Define a SmartThings dishwasher washing option switch."""

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            client,
            device,
            entity_description,
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS,
            MAIN,
            {
                Capability.REMOTE_CONTROL_STATUS,
                Capability.DISHWASHER_OPERATING_STATE,
                Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE,
                Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE_DETAILS,
            },
        )

    def _validate_before_execute(self) -> None:
        """Validate that the switch command can be executed."""
        if (
            self.get_attribute_value(
                Capability.REMOTE_CONTROL_STATUS, Attribute.REMOTE_CONTROL_ENABLED
            )
            == "false"
        ):
            raise ServiceValidationError(
                "Can only be updated when remote control is enabled"
            )
        if (
            self.get_attribute_value(
                Capability.DISHWASHER_OPERATING_STATE, Attribute.MACHINE_STATE
            )
            != "stop"
        ):
            raise ServiceValidationError(
                "Can only be updated when dishwasher machine state is stop"
            )
        selected_course = self.get_attribute_value(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE, Attribute.WASHING_COURSE
        )
        course_details = self.get_attribute_value(
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_COURSE_DETAILS,
            Attribute.PREDEFINED_COURSES,
        )
        course_settable: list[bool] = next(
            (
                detail["options"][self.entity_description.status_attribute]["settable"]
                for detail in course_details
                if detail["courseName"] == selected_course
            ),
            [],
        )
        if not course_settable:
            raise ServiceValidationError("Option is not supported by selected cycle")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._validate_before_execute()
        await super().async_turn_off(**kwargs)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._validate_before_execute()
        await super().async_turn_on(**kwargs)

    def _current_state(self) -> Any:
        return super()._current_state()["value"]
