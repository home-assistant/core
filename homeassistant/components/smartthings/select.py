"""Support for select entities through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass

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
    ) -> None:
        """Initialize the instance."""
        capabilities = {entity_description.key}
        if entity_description.requires_remote_control_status:
            capabilities.add(Capability.REMOTE_CONTROL_STATUS)
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
        return options

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        option = self.get_attribute_value(
            self.entity_description.key, self.entity_description.status_attribute
        )
        if self.entity_description.options_map:
            option = self.entity_description.options_map.get(option)
        return option

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
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
        if self.entity_description.options_map:
            option = next(
                (
                    key
                    for key, value in self.entity_description.options_map.items()
                    if value == option
                ),
                option,
            )
        await self.execute_device_command(
            self.entity_description.key,
            self.entity_description.command,
            option,
        )
