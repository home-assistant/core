"""Support for button entities through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pysmartthings import Attribute, Capability, Category, Command, SmartThings

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import DOMAIN, MAIN
from .entity import SmartThingsEntity


@dataclass(frozen=True, kw_only=True)
class SmartThingsButtonDescription(ButtonEntityDescription):
    """Class describing SmartThings button entities."""

    key: Capability
    command: Command
    command_identifier: str | None = None
    components: list[str] | None = None
    argument: int | str | list[Any] | dict[str, Any] | None = None
    requires_remote_control_status: bool = False
    requires_dishwasher_machine_state: set[str] | None = None


CAPABILITIES_TO_BUTTONS: dict[Capability | str, SmartThingsButtonDescription] = {
    Capability.OVEN_OPERATING_STATE: SmartThingsButtonDescription(
        key=Capability.OVEN_OPERATING_STATE,
        translation_key="stop",
        command=Command.STOP,
    ),
    Capability.CUSTOM_WATER_FILTER: SmartThingsButtonDescription(
        key=Capability.CUSTOM_WATER_FILTER,
        translation_key="reset_water_filter",
        command=Command.RESET_WATER_FILTER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    Capability.SAMSUNG_CE_HOOD_FILTER: SmartThingsButtonDescription(
        key=Capability.SAMSUNG_CE_HOOD_FILTER,
        translation_key="reset_hood_filter",
        command=Command.RESET_HOOD_FILTER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    Capability.CUSTOM_HEPA_FILTER: SmartThingsButtonDescription(
        key=Capability.CUSTOM_HEPA_FILTER,
        translation_key="reset_hepa_filter",
        command=Command.RESET_HEPA_FILTER,
        entity_category=EntityCategory.DIAGNOSTIC,
        components=[MAIN, "station"],
    ),
}


DISHWASHER_OPERATION_COMMANDS_TO_BUTTONS: dict[
    Command | str, SmartThingsButtonDescription
] = {
    Command.CANCEL: SmartThingsButtonDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        translation_key="cancel",
        command_identifier="drain",
        command=Command.CANCEL,
        argument=[True],
        requires_remote_control_status=True,
    ),
    Command.PAUSE: SmartThingsButtonDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        translation_key="pause",
        command=Command.PAUSE,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"run"},
    ),
    Command.RESUME: SmartThingsButtonDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        translation_key="resume",
        command=Command.RESUME,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"pause"},
    ),
    Command.START: SmartThingsButtonDescription(
        key=Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        translation_key="start",
        command=Command.START,
        requires_remote_control_status=True,
        requires_dishwasher_machine_state={"stop"},
    ),
}

DISHWASHER_CANCEL_AND_DRAIN_BUTTON = SmartThingsButtonDescription(
    key=Capability.CUSTOM_SUPPORTED_OPTIONS,
    translation_key="cancel_and_drain",
    command_identifier="89",
    command=Command.SET_COURSE,
    argument="89",
    requires_remote_control_status=True,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add button entities for a config entry."""
    entry_data = entry.runtime_data
    entities: list[SmartThingsEntity] = []
    entities.extend(
        SmartThingsButtonEntity(
            entry_data.client, device, description, Capability(capability), component
        )
        for capability, description in CAPABILITIES_TO_BUTTONS.items()
        for device in entry_data.devices.values()
        for component in description.components or [MAIN]
        if component in device.status and capability in device.status[component]
    )
    entities.extend(
        SmartThingsButtonEntity(
            entry_data.client,
            device,
            description,
            Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        )
        for device in entry_data.devices.values()
        if Capability.SAMSUNG_CE_DISHWASHER_OPERATION in device.status[MAIN]
        for description in DISHWASHER_OPERATION_COMMANDS_TO_BUTTONS.values()
    )
    entities.extend(
        SmartThingsButtonEntity(
            entry_data.client,
            device,
            DISHWASHER_CANCEL_AND_DRAIN_BUTTON,
            Capability.CUSTOM_SUPPORTED_OPTIONS,
        )
        for device in entry_data.devices.values()
        if (
            device.device.components[MAIN].manufacturer_category == Category.DISHWASHER
            and Capability.CUSTOM_SUPPORTED_OPTIONS in device.status[MAIN]
        )
    )
    async_add_entities(entities)


class SmartThingsButtonEntity(SmartThingsEntity, ButtonEntity):
    """Define a SmartThings button."""

    entity_description: SmartThingsButtonDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsButtonDescription,
        capability: Capability,
        component: str = MAIN,
    ) -> None:
        """Initialize the instance."""
        capabilities = set()
        if entity_description.requires_remote_control_status:
            capabilities.add(Capability.REMOTE_CONTROL_STATUS)
        if entity_description.requires_dishwasher_machine_state:
            capabilities.add(Capability.DISHWASHER_OPERATING_STATE)
        super().__init__(client, device, capabilities)
        self.entity_description = entity_description
        self.button_capability = capability
        self._attr_unique_id = f"{device.device.device_id}_{component}_{entity_description.key}_{entity_description.command}"
        if entity_description.command_identifier is not None:
            self._attr_unique_id += f"_{entity_description.command_identifier}"

    async def async_press(self) -> None:
        """Press the button."""
        self._validate_before_execute()
        await self.execute_device_command(
            self.button_capability,
            self.entity_description.command,
            self.entity_description.argument,
        )

    def _validate_before_execute(self) -> None:
        """Validate that the command can be executed."""
        if (
            self.entity_description.requires_remote_control_status
            and self.get_attribute_value(
                Capability.REMOTE_CONTROL_STATUS, Attribute.REMOTE_CONTROL_ENABLED
            )
            == "false"
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="remote_control_status"
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
