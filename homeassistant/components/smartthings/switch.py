"""Support for switches through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Callable
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
    status_fn: Callable[[Any], str | bool] = lambda value: value
    component_translation_key: dict[str, str] | None = None
    on_key: str | bool = "on"
    on_command: Command = Command.ON
    off_command: Command = Command.OFF
    requires_remote_control_status: bool = False
    requires_dishwasher_machine_state: set[str] | None = None


@dataclass(frozen=True, kw_only=True)
class SmartThingsCommandSwitchEntityDescription(SmartThingsSwitchEntityDescription):
    """Describe a SmartThings switch entity."""

    command: Command
    off_key: str | bool = "off"


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
    Attribute | str, SmartThingsSwitchEntityDescription
] = {
    Attribute.ADD_RINSE: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.ADD_RINSE,
        translation_key="add_rinse",
        status_attribute=Attribute.ADD_RINSE,
        status_fn=lambda value: value["value"],
        command=Command.SET_ADD_RINSE,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.DRY_PLUS: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.DRY_PLUS,
        translation_key="dry_plus",
        status_attribute=Attribute.DRY_PLUS,
        status_fn=lambda value: value["value"],
        command=Command.SET_DRY_PLUS,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.HEATED_DRY: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.HEATED_DRY,
        translation_key="heated_dry",
        status_attribute=Attribute.HEATED_DRY,
        status_fn=lambda value: value["value"],
        command=Command.SET_HEATED_DRY,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.HIGH_TEMP_WASH: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.HIGH_TEMP_WASH,
        translation_key="high_temp_wash",
        status_attribute=Attribute.HIGH_TEMP_WASH,
        status_fn=lambda value: value["value"],
        command=Command.SET_HIGH_TEMP_WASH,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.HOT_AIR_DRY: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.HOT_AIR_DRY,
        translation_key="hot_air_dry",
        status_attribute=Attribute.HOT_AIR_DRY,
        status_fn=lambda value: value["value"],
        command=Command.SET_HOT_AIR_DRY,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.MULTI_TAB: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.MULTI_TAB,
        translation_key="multi_tab",
        status_attribute=Attribute.MULTI_TAB,
        status_fn=lambda value: value["value"],
        command=Command.SET_MULTI_TAB,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.RINSE_PLUS: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.RINSE_PLUS,
        translation_key="rinse_plus",
        status_attribute=Attribute.RINSE_PLUS,
        status_fn=lambda value: value["value"],
        command=Command.SET_RINSE_PLUS,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.SANITIZE: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.SANITIZE,
        translation_key="sanitize",
        status_attribute=Attribute.SANITIZE,
        status_fn=lambda value: value["value"],
        command=Command.SET_SANITIZE,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.SANITIZING_WASH: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.SANITIZING_WASH,
        translation_key="sanitizing_wash",
        status_attribute=Attribute.SANITIZING_WASH,
        status_fn=lambda value: value["value"],
        command=Command.SET_SANITIZING_WASH,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.SELECTED_ZONE: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.SELECTED_ZONE,
        translation_key="selected_zone",
        status_attribute=Attribute.SELECTED_ZONE,
        status_fn=lambda value: value["value"],
        command=Command.SET_SELECTED_ZONE,
        on_key="lower",
        off_key="all",
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.SPEED_BOOSTER: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.SPEED_BOOSTER,
        translation_key="speed_booster",
        status_attribute=Attribute.SPEED_BOOSTER,
        status_fn=lambda value: value["value"],
        command=Command.SET_SPEED_BOOSTER,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.STEAM_SOAK: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.STEAM_SOAK,
        translation_key="steam_soak",
        status_attribute=Attribute.STEAM_SOAK,
        status_fn=lambda value: value["value"],
        command=Command.SET_STEAM_SOAK,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.STORM_WASH: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.STORM_WASH,
        translation_key="storm_wash",
        status_attribute=Attribute.STORM_WASH,
        status_fn=lambda value: value["value"],
        command=Command.SET_STORM_WASH,
        on_key=True,
        off_key=False,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
    Attribute.ZONE_BOOSTER: SmartThingsCommandSwitchEntityDescription(
        key=Attribute.ZONE_BOOSTER,
        translation_key="zone_booster",
        status_attribute=Attribute.ZONE_BOOSTER,
        status_fn=lambda value: value["value"],
        command=Command.SET_ZONE_BOOSTER,
        on_key="left",
        off_key="none",
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
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
        SmartThingsCommandSwitch(
            entry_data.client,
            device,
            DISHWASHER_WASHING_OPTIONS_TO_SWITCHES[attribute],
            Capability.SAMSUNG_CE_DISHWASHER_WASHING_OPTIONS,
            component,
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
    ) -> None:
        """Initialize the switch."""
        capabilities = {capability}
        if entity_description.requires_remote_control_status:
            capabilities.add(Capability.REMOTE_CONTROL_STATUS)
        if entity_description.requires_dishwasher_machine_state:
            capabilities.add(Capability.DISHWASHER_OPERATING_STATE)
        super().__init__(client, device, capabilities, component=component)
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
        self._validate_before_execute()
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.off_command,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._validate_before_execute()
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.on_command,
        )

    def _validate_before_execute(self) -> None:
        """Validate that the switch command can be executed."""
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
        if (
            self.entity_description.requires_dishwasher_machine_state
            and self.get_attribute_value(
                Capability.DISHWASHER_OPERATING_STATE, Attribute.MACHINE_STATE
            )
            not in self.entity_description.requires_dishwasher_machine_state
        ):
            state_list = " or ".join(
                self.entity_description.requires_dishwasher_machine_state
            )
            raise ServiceValidationError(
                f"Can only be updated when dishwasher machine state is {state_list}"
            )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        status = self.get_attribute_value(
            self.switch_capability, self.entity_description.status_attribute
        )
        return (
            self.entity_description.status_fn(status) == self.entity_description.on_key
        )


class SmartThingsCommandSwitch(SmartThingsSwitch):
    """Define a SmartThings command switch."""

    entity_description: SmartThingsCommandSwitchEntityDescription

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._validate_before_execute()
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.command,
            self.entity_description.off_key,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._validate_before_execute()
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.command,
            self.entity_description.on_key,
        )
