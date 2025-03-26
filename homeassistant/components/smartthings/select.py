"""Support for select entities through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity


@dataclass(frozen=True, kw_only=True)
class SmartThingsSelectDescription(SelectEntityDescription):
    """Class describing SmartThings select entities."""

    key: Capability
    requires_remote_control_status: bool
    options_attribute: Attribute
    status_attribute: Attribute
    command: Command


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
    ),
    Capability.WASHER_OPERATING_STATE: SmartThingsSelectDescription(
        key=Capability.WASHER_OPERATING_STATE,
        name=None,
        translation_key="operating_state",
        requires_remote_control_status=True,
        options_attribute=Attribute.SUPPORTED_MACHINE_STATES,
        status_attribute=Attribute.MACHINE_STATE,
        command=Command.SET_MACHINE_STATE,
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
        SmartThingsSelectEntity(
            entry_data.client, device, CAPABILITIES_TO_SELECT[capability]
        )
        for device in entry_data.devices.values()
        for capability in device.status[MAIN]
        if capability in CAPABILITIES_TO_SELECT
    )


class SmartThingsSelectEntity(SmartThingsEntity, SelectEntity):
    """Define a SmartThings select."""

    entity_description: SmartThingsSelectDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSelectDescription,
    ) -> None:
        """Initialize the instance."""
        capabilities = {entity_description.key}
        if entity_description.requires_remote_control_status:
            capabilities.add(Capability.REMOTE_CONTROL_STATUS)
        super().__init__(client, device, capabilities)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.device.device_id}_{MAIN}_{entity_description.key}_{entity_description.status_attribute}_{entity_description.status_attribute}"

    @property
    def options(self) -> list[str]:
        """Return the list of options."""
        return self.get_attribute_value(
            self.entity_description.key, self.entity_description.options_attribute
        )

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.get_attribute_value(
            self.entity_description.key, self.entity_description.status_attribute
        )

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
        await self.execute_device_command(
            self.entity_description.key,
            self.entity_description.command,
            option,
        )
