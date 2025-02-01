"""Provides a select platform for Home Connect."""

from typing import cast

from aiohomeconnect.model import EventKey, ProgramKey
from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import APPLIANCES_WITH_PROGRAMS, DOMAIN, SVE_TRANSLATION_PLACEHOLDER_PROGRAM
from .coordinator import (
    HomeConnectApplianceData,
    HomeConnectConfigEntry,
    HomeConnectCoordinator,
)
from .entity import HomeConnectEntity
from .utils import bsh_key_to_translation_key, get_dict_from_home_connect_error

TRANSLATION_KEYS_PROGRAMS_MAP = {
    bsh_key_to_translation_key(program.value): cast(ProgramKey, program)
    for program in ProgramKey
    if program != ProgramKey.UNKNOWN
}

PROGRAMS_TRANSLATION_KEYS_MAP = {
    value: key for key, value in TRANSLATION_KEYS_PROGRAMS_MAP.items()
}

PROGRAM_SELECT_ENTITY_DESCRIPTIONS = (
    SelectEntityDescription(
        key=EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
        translation_key="active_program",
    ),
    SelectEntityDescription(
        key=EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
        translation_key="selected_program",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect select entities."""
    known_enitiy_unique_ids: dict[str, str] = {}

    def get_entities_for_appliance(
        appliance: HomeConnectApplianceData,
    ) -> list[HomeConnectProgramSelectEntity]:
        """Get a list of entities."""
        return (
            [
                HomeConnectProgramSelectEntity(entry.runtime_data, appliance, desc)
                for desc in PROGRAM_SELECT_ENTITY_DESCRIPTIONS
            ]
            if appliance.info.type in APPLIANCES_WITH_PROGRAMS
            else []
        )

    for appliance in entry.runtime_data.data.values():
        entities = get_entities_for_appliance(appliance)
        known_enitiy_unique_ids.update(
            {cast(str, entity.unique_id): appliance.info.ha_id for entity in entities}
        )
        async_add_entities(entities)

    def handle_paired_or_connected_appliance() -> None:
        """Handle new paired appliance or a appliance that has been connected."""
        for appliance in entry.runtime_data.data.values():
            entities_to_add = [
                entity
                for entity in get_entities_for_appliance(appliance)
                if cast(str, entity.unique_id) not in known_enitiy_unique_ids
            ]
            known_enitiy_unique_ids.update(
                {
                    cast(str, entity.unique_id): appliance.info.ha_id
                    for entity in entities_to_add
                }
            )
            async_add_entities(entities_to_add)

    def handle_depaired_appliance() -> None:
        """Handle removed appliance."""
        for entity_unique_id, appliance_id in known_enitiy_unique_ids.copy().items():
            if appliance_id not in entry.runtime_data.data:
                known_enitiy_unique_ids.pop(entity_unique_id, None)

    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            handle_paired_or_connected_appliance,
            (
                EventKey.BSH_COMMON_APPLIANCE_PAIRED,
                EventKey.BSH_COMMON_APPLIANCE_CONNECTED,
            ),
        )
    )
    entry.async_on_unload(
        entry.runtime_data.async_add_special_listener(
            handle_depaired_appliance,
            (EventKey.BSH_COMMON_APPLIANCE_DEPAIRED,),
        ),
    )


class HomeConnectProgramSelectEntity(HomeConnectEntity, SelectEntity):
    """Select class for Home Connect programs."""

    def __init__(
        self,
        coordinator: HomeConnectCoordinator,
        appliance: HomeConnectApplianceData,
        desc: SelectEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            appliance,
            desc,
        )
        self._attr_options = [
            PROGRAMS_TRANSLATION_KEYS_MAP[program.key]
            for program in appliance.programs
            if program.key != ProgramKey.UNKNOWN
        ]
        self.start_on_select = desc.key == EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM
        self._attr_current_option = None

    def update_native_value(self) -> None:
        """Set the program value."""
        event = self.appliance.events.get(cast(EventKey, self.bsh_key))
        self._attr_current_option = (
            PROGRAMS_TRANSLATION_KEYS_MAP.get(cast(ProgramKey, event.value))
            if event
            else None
        )

    async def async_select_option(self, option: str) -> None:
        """Select new program."""
        program_key = TRANSLATION_KEYS_PROGRAMS_MAP[option]
        try:
            if self.start_on_select:
                await self.coordinator.client.start_program(
                    self.appliance.info.ha_id, program_key=program_key
                )
            else:
                await self.coordinator.client.set_selected_program(
                    self.appliance.info.ha_id, program_key=program_key
                )
        except HomeConnectError as err:
            if self.start_on_select:
                translation_key = "start_program"
            else:
                translation_key = "select_program"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_PROGRAM: program_key.value,
                },
            ) from err
