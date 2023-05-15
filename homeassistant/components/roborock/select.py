"""Support for Roborock select."""
from collections.abc import Callable
from dataclasses import dataclass

from roborock.code_mappings import RoborockMopIntensityCode, RoborockMopModeCode
from roborock.containers import Status
from roborock.exceptions import RoborockException
from roborock.typing import RoborockCommand

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .models import RoborockHassDeviceInfo


@dataclass
class RoborockSelectDescriptionMixin:
    """Define an entity description mixin for select entities."""

    api_command: RoborockCommand
    value_fn: Callable[[Status], str]
    options_lambda: Callable[[str], list[int]]


@dataclass
class RoborockSelectDescription(
    SelectEntityDescription, RoborockSelectDescriptionMixin
):
    """Class to describe an Roborock select entity."""


SELECT_DESCRIPTIONS: list[RoborockSelectDescription] = [
    RoborockSelectDescription(
        key="water_box_mode",
        translation_key="mop_intensity",
        options=RoborockMopIntensityCode.values(),
        api_command=RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
        value_fn=lambda data: data.water_box_mode,
        options_lambda=lambda data: [
            k for k, v in RoborockMopIntensityCode.items() if v == data
        ],
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        options=RoborockMopModeCode.values(),
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda data: data.mop_mode,
        options_lambda=lambda data: [
            k for k, v in RoborockMopModeCode.items() if v == data
        ],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock select platform."""

    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RoborockSelectEntity(
            f"{description.key}_{slugify(device_id)}",
            device_info,
            coordinator,
            description,
        )
        for device_id, device_info in coordinator.devices_info.items()
        for description in SELECT_DESCRIPTIONS
    )


class RoborockSelectEntity(RoborockCoordinatedEntity, SelectEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockSelectDescription

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSelectDescription,
    ) -> None:
        """Create a select entity."""
        self.entity_description = entity_description
        super().__init__(unique_id, device_info, coordinator)

    async def async_select_option(self, option: str) -> None:
        """Set the mop intensity."""
        try:
            await self.send(
                self.entity_description.api_command,
                self.entity_description.options_lambda(option),
            )
        except RoborockException as err:
            raise HomeAssistantError(
                f"Error while setting {self.entity_description.key} to {option}"
            ) from err

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        return self.entity_description.value_fn(self._device_status)
