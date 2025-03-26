"""Support for switches through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pysmartthings import Attribute, Capability, Category, Command, SmartThings

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from . import FullDevice, SmartThingsConfigEntry
from .const import DOMAIN, MAIN
from .entity import SmartThingsEntity

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


@dataclass(frozen=True, kw_only=True)
class SmartThingsSwitchEntityDescription(SwitchEntityDescription):
    """Describe a SmartThings switch entity."""

    status_attribute: Attribute


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
    )
}
CAPABILITY_TO_SWITCHES: dict[Capability | str, SmartThingsSwitchEntityDescription] = {
    Capability.SAMSUNG_CE_WASHER_BUBBLE_SOAK: SmartThingsSwitchEntityDescription(
        key=Capability.SAMSUNG_CE_WASHER_BUBBLE_SOAK,
        translation_key="bubble_soak",
        status_attribute=Attribute.STATUS,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add switches for a config entry."""
    entry_data = entry.runtime_data
    entities: list[SmartThingsEntity] = [
        SmartThingsSwitch(entry_data.client, device, SWITCH, Capability.SWITCH)
        for device in entry_data.devices.values()
        if Capability.SWITCH in device.status[MAIN]
        and not any(capability in device.status[MAIN] for capability in CAPABILITIES)
        and not all(capability in device.status[MAIN] for capability in AC_CAPABILITIES)
    ]
    entities.extend(
        SmartThingsCommandSwitch(
            entry_data.client,
            device,
            description,
            Capability(capability),
        )
        for device in entry_data.devices.values()
        for capability, description in CAPABILITY_TO_COMMAND_SWITCHES.items()
        if capability in device.status[MAIN]
    )
    entities.extend(
        SmartThingsSwitch(
            entry_data.client,
            device,
            description,
            Capability(capability),
        )
        for device in entry_data.devices.values()
        for capability, description in CAPABILITY_TO_SWITCHES.items()
        if capability in device.status[MAIN]
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
    ) -> None:
        """Initialize the switch."""
        super().__init__(client, device, {capability})
        self.entity_description = entity_description
        self.switch_capability = capability
        self._attr_unique_id = device.device.device_id
        if capability is not Capability.SWITCH:
            self._attr_unique_id = f"{device.device.device_id}_{MAIN}_{capability}"

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

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        if self.entity_description != SWITCH or self.device.device.components[
            MAIN
        ].manufacturer_category not in {Category.DRYER, Category.WASHER}:
            return
        automations = automations_with_entity(self.hass, self.entity_id)
        scripts = scripts_with_entity(self.hass, self.entity_id)
        items = automations + scripts
        if not items:
            return

        entity_reg: er.EntityRegistry = er.async_get(self.hass)
        entity_automations = [
            automation_entity
            for automation_id in automations
            if (automation_entity := entity_reg.async_get(automation_id))
        ]
        entity_scripts = [
            script_entity
            for script_id in scripts
            if (script_entity := entity_reg.async_get(script_id))
        ]

        items_list = [
            f"- [{item.original_name}](/config/automation/edit/{item.unique_id})"
            for item in entity_automations
        ] + [
            f"- [{item.original_name}](/config/script/edit/{item.unique_id})"
            for item in entity_scripts
        ]

        async_create_issue(
            self.hass,
            DOMAIN,
            f"deprecated_switch_{self.entity_id}",
            breaks_in_ha_version="2025.10.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_switch_appliance",
            translation_placeholders={
                "entity": self.entity_id,
                "items": "\n".join(items_list),
            },
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if self.entity_description != SWITCH or self.device.device.components[
            MAIN
        ].manufacturer_category not in {Category.DRYER, Category.WASHER}:
            return
        async_delete_issue(self.hass, DOMAIN, f"deprecated_switch_{self.entity_id}")


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
