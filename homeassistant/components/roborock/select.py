"""Support for Roborock select."""

from collections.abc import Callable
from dataclasses import dataclass

from roborock.containers import Status
from roborock.roborock_message import RoborockDataProtocol
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity


@dataclass(frozen=True, kw_only=True)
class RoborockSelectDescription(SelectEntityDescription):
    """Class to describe a Roborock select entity."""

    # The command that the select entity will send to the api.
    api_command: RoborockCommand
    # Gets the current value of the select entity.
    value_fn: Callable[[Status], str | None]
    # Gets all options of the select entity.
    options_lambda: Callable[[Status], list[str] | None]
    # Takes the value from the select entity and converts it for the api.
    parameter_lambda: Callable[[str, Status], list[int]]

    protocol_listener: RoborockDataProtocol | None = None


SELECT_DESCRIPTIONS: list[RoborockSelectDescription] = [
    RoborockSelectDescription(
        key="water_box_mode",
        translation_key="mop_intensity",
        api_command=RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
        value_fn=lambda data: data.water_box_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda data: data.water_box_mode.keys()
        if data.water_box_mode is not None
        else None,
        parameter_lambda=lambda key, status: [status.get_mop_intensity_code(key)],
        protocol_listener=RoborockDataProtocol.WATER_BOX_MODE,
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda data: data.mop_mode_name,
        entity_category=EntityCategory.CONFIG,
        options_lambda=lambda data: data.mop_mode.keys()
        if data.mop_mode is not None
        else None,
        parameter_lambda=lambda key, status: [status.get_mop_mode_code(key)],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock select platform."""

    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RoborockSelectEntity(
            f"{description.key}_{slugify(device_id)}", coordinator, description, options
        )
        for device_id, coordinator in coordinators.items()
        for description in SELECT_DESCRIPTIONS
        if (
            options := description.options_lambda(
                coordinator.roborock_device_info.props.status
            )
        )
        is not None
    )


class RoborockSelectEntity(RoborockCoordinatedEntity, SelectEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockSelectDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSelectDescription,
        options: list[str],
    ) -> None:
        """Create a select entity."""
        self.entity_description = entity_description
        super().__init__(unique_id, coordinator, entity_description.protocol_listener)
        self._attr_options = options

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.send(
            self.entity_description.api_command,
            self.entity_description.parameter_lambda(option, self._device_status),
        )

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        return self.entity_description.value_fn(self._device_status)
