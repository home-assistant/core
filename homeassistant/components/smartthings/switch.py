"""Support for switches through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
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


@dataclass(frozen=True, kw_only=True)
class SmartThingsCommandSwitchEntityDescription(SmartThingsSwitchEntityDescription):
    """Describe a SmartThings switch entity."""

    command: Command


SWITCH = SmartThingsSwitchEntityDescription(
    key=Capability.SWITCH,
    status_attribute=Attribute.SWITCH,
    name=None,
)
CAPABILITY_TO_COMMAND_SWITCHES: dict[
    Capability | str, SmartThingsCommandSwitchEntityDescription
] = {
    Capability.CUSTOM_DRYER_WRINKLE_PREVENT: SmartThingsCommandSwitchEntityDescription(
        key=Capability.CUSTOM_DRYER_WRINKLE_PREVENT,
        translation_key="wrinkle_prevent",
        status_attribute=Attribute.DRYER_WRINKLE_PREVENT,
        command=Command.SET_DRYER_WRINKLE_PREVENT,
        entity_category=EntityCategory.CONFIG,
    )
}
CAPABILITY_TO_SWITCHES: dict[Capability | str, SmartThingsSwitchEntityDescription] = {
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
        },
    ),
    Capability.SAMSUNG_CE_SABBATH_MODE: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_SABBATH_MODE,
        translation_key="sabbath_mode",
        status_attribute=Attribute.STATUS,
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
            if media_player or appliance:
                issue = "media_player" if media_player else "appliance"
                if deprecate_entity(
                    hass,
                    entity_registry,
                    SWITCH_DOMAIN,
                    f"{device.device.device_id}_{MAIN}_{Capability.SWITCH}_{Attribute.SWITCH}_{Attribute.SWITCH}",
                    f"deprecated_switch_{issue}",
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
        super().__init__(client, device, {capability}, component=component)
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
            Command.OFF,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.execute_device_command(
            self.switch_capability,
            Command.ON,
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return (
            self.get_attribute_value(
                self.switch_capability, self.entity_description.status_attribute
            )
            == "on"
        )


class SmartThingsCommandSwitch(SmartThingsSwitch):
    """Define a SmartThings command switch."""

    entity_description: SmartThingsCommandSwitchEntityDescription

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.command,
            "off",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.execute_device_command(
            self.switch_capability,
            self.entity_description.command,
            "on",
        )
