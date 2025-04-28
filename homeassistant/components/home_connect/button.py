"""Provides button entities for Home Connect."""

from aiohomeconnect.model import CommandKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import APPLIANCES_WITH_PROGRAMS, DOMAIN
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import get_dict_from_home_connect_error

PARALLEL_UPDATES = 1


class HomeConnectCommandButtonEntityDescription(ButtonEntityDescription):
    """Describes Home Connect button entity."""

    key: CommandKey


COMMAND_BUTTONS = (
    HomeConnectCommandButtonEntityDescription(
        key=CommandKey.BSH_COMMON_OPEN_DOOR,
        translation_key="open_door",
    ),
    HomeConnectCommandButtonEntityDescription(
        key=CommandKey.BSH_COMMON_PARTLY_OPEN_DOOR,
        translation_key="partly_open_door",
    ),
    HomeConnectCommandButtonEntityDescription(
        key=CommandKey.BSH_COMMON_PAUSE_PROGRAM,
        translation_key="pause_program",
    ),
    HomeConnectCommandButtonEntityDescription(
        key=CommandKey.BSH_COMMON_RESUME_PROGRAM,
        translation_key="resume_program",
    ),
)


def _get_entities_for_appliance(
    entry: HomeConnectConfigEntry,
    appliance: HomeConnectApplianceData,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    entities: list[HomeConnectEntity] = []
    entities.extend(
        HomeConnectCommandButtonEntity(entry.runtime_data, appliance, description)
        for description in COMMAND_BUTTONS
        if description.key in appliance.commands
    )
    if appliance.info.type in APPLIANCES_WITH_PROGRAMS:
        entities.append(
            HomeConnectStopProgramButtonEntity(entry.runtime_data, appliance)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect button entities."""
    setup_home_connect_entry(
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectButtonEntity(HomeConnectEntity, ButtonEntity):
    """Describes Home Connect button entity."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: ButtonEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            appliance,
            desc,
            (appliance.info.ha_id,),
        )

    def update_native_value(self) -> None:
        """Set the value of the entity."""


class HomeConnectCommandButtonEntity(HomeConnectButtonEntity):
    """Button entity for Home Connect commands."""

    entity_description: HomeConnectCommandButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        try:
            await self.coordinator.client.put_command(
                self.appliance.info.ha_id,
                command_key=self.entity_description.key,
                value=True,
            )
        except HomeConnectError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="execute_command",
                translation_placeholders={
                    **get_dict_from_home_connect_error(error),
                    "command": self.entity_description.key,
                },
            ) from error


class HomeConnectStopProgramButtonEntity(HomeConnectButtonEntity):
    """Button entity for stopping a program."""

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            appliance,
            ButtonEntityDescription(
                key="StopProgram",
                translation_key="stop_program",
            ),
        )

    async def async_press(self) -> None:
        """Press the button."""
        try:
            await self.coordinator.client.stop_program(self.appliance.info.ha_id)
        except HomeConnectError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stop_program",
                translation_placeholders=get_dict_from_home_connect_error(error),
            ) from error
