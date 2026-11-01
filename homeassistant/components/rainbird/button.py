"""The button platform for rainbird."""

from typing import override

from pyrainbird.exceptions import RainbirdApiException, RainbirdDeviceBusyException
from pyrainbird.timeline import ProgramId

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import RainbirdUpdateCoordinator
from .types import RainbirdConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RainbirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird button platform."""
    data = config_entry.runtime_data
    async_add_entities(
        RainbirdProgramButton(data.coordinator, program)
        for program in range(data.model_info.model_info.max_programs)
    )


class RainbirdProgramButton(CoordinatorEntity[RainbirdUpdateCoordinator], ButtonEntity):
    """A button that manually starts a program configured on the controller."""

    _attr_translation_key = "run_program"
    _attr_has_entity_name = True

    def __init__(self, coordinator: RainbirdUpdateCoordinator, program: int) -> None:
        """Initialize the Rain Bird program button."""
        super().__init__(coordinator)
        self._program = program
        program_name = ProgramId(program).name
        self._attr_translation_placeholders = {"program": program_name}
        if coordinator.unique_id is not None:
            self._attr_unique_id = f"{coordinator.unique_id}-program-{program}"
            self._attr_device_info = coordinator.device_info
        else:
            self._attr_name = f"{coordinator.device_name} Run {program_name}"

    @override
    async def async_press(self) -> None:
        """Start the program."""
        try:
            await self.coordinator.controller.set_program(self._program)
        except RainbirdDeviceBusyException as err:
            raise HomeAssistantError(
                "Rain Bird device is busy; Wait and try again"
            ) from err
        except RainbirdApiException as err:
            raise HomeAssistantError("Rain Bird device failure") from err

        # Zone switches reflect the running program after the next refresh.
        await self.coordinator.async_request_refresh()
