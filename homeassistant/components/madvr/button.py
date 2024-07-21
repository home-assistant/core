"""Binary sensor entities for the madVR integration."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MadVRConfigEntry
from .const import ButtonCommands
from .coordinator import MadVRCoordinator
from .entity import MadVREntity


@dataclass(frozen=True, kw_only=True)
class MadvrButtonEntityDescription(ButtonEntityDescription):
    """Describe madVR button entity."""

    command: Iterable[str]


COMMANDS: tuple[MadvrButtonEntityDescription, ...] = (
    MadvrButtonEntityDescription(
        key=ButtonCommands.reset_temporary.name,
        translation_key=ButtonCommands.reset_temporary.name,
        command=ButtonCommands.reset_temporary.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.openmenu_info.name,
        translation_key=ButtonCommands.openmenu_info.name,
        command=ButtonCommands.openmenu_info.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.openmenu_settings.name,
        translation_key=ButtonCommands.openmenu_settings.name,
        command=ButtonCommands.openmenu_settings.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.openmenu_configuration.name,
        translation_key=ButtonCommands.openmenu_configuration.name,
        command=ButtonCommands.openmenu_configuration.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.openmenu_profiles.name,
        translation_key=ButtonCommands.openmenu_profiles.name,
        command=ButtonCommands.openmenu_profiles.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.openmenu_testpatterns.name,
        translation_key=ButtonCommands.openmenu_testpatterns.name,
        command=ButtonCommands.openmenu_testpatterns.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.toggle_tonemap.name,
        translation_key=ButtonCommands.toggle_tonemap.name,
        command=ButtonCommands.toggle_tonemap.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.toggle_highlightrecovery.name,
        translation_key=ButtonCommands.toggle_highlightrecovery.name,
        command=ButtonCommands.toggle_highlightrecovery.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.toggle_contrastrecovery.name,
        translation_key=ButtonCommands.toggle_contrastrecovery.name,
        command=ButtonCommands.toggle_contrastrecovery.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.toggle_shadowrecovery.name,
        translation_key=ButtonCommands.toggle_shadowrecovery.name,
        command=ButtonCommands.toggle_shadowrecovery.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.toggle_3dlut.name,
        translation_key=ButtonCommands.toggle_3dlut.name,
        command=ButtonCommands.toggle_3dlut.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.toggle_screenboundaries.name,
        translation_key=ButtonCommands.toggle_screenboundaries.name,
        command=ButtonCommands.toggle_screenboundaries.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.toggle_histogram.name,
        translation_key=ButtonCommands.toggle_histogram.name,
        command=ButtonCommands.toggle_histogram.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.toggle_debugosd.name,
        translation_key=ButtonCommands.toggle_debugosd.name,
        command=ButtonCommands.toggle_debugosd.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.refresh_licenseinfo.name,
        translation_key=ButtonCommands.refresh_licenseinfo.name,
        command=ButtonCommands.refresh_licenseinfo.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.force1080p60output.name,
        translation_key=ButtonCommands.force1080p60output.name,
        command=ButtonCommands.force1080p60output.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_left.name,
        translation_key=ButtonCommands.button_left.name,
        command=ButtonCommands.button_left.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_right.name,
        translation_key=ButtonCommands.button_right.name,
        command=ButtonCommands.button_right.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_up.name,
        translation_key=ButtonCommands.button_up.name,
        command=ButtonCommands.button_up.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_down.name,
        translation_key=ButtonCommands.button_down.name,
        command=ButtonCommands.button_down.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_ok.name,
        translation_key=ButtonCommands.button_ok.name,
        command=ButtonCommands.button_ok.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_back.name,
        translation_key=ButtonCommands.button_back.name,
        command=ButtonCommands.button_back.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_red.name,
        translation_key=ButtonCommands.button_red.name,
        command=ButtonCommands.button_red.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_green.name,
        translation_key=ButtonCommands.button_green.name,
        command=ButtonCommands.button_green.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_blue.name,
        translation_key=ButtonCommands.button_blue.name,
        command=ButtonCommands.button_blue.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_yellow.name,
        translation_key=ButtonCommands.button_yellow.name,
        command=ButtonCommands.button_yellow.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_magenta.name,
        translation_key=ButtonCommands.button_magenta.name,
        command=ButtonCommands.button_magenta.value,
    ),
    MadvrButtonEntityDescription(
        key=ButtonCommands.button_cyan.name,
        translation_key=ButtonCommands.button_cyan.name,
        command=ButtonCommands.button_cyan.value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadVRConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        MadvrButtonEntity(coordinator, description) for description in COMMANDS
    )


class MadvrButtonEntity(MadVREntity, ButtonEntity):
    """Base class for madVR binary sensors."""

    def __init__(
        self,
        coordinator: MadVRCoordinator,
        description: MadvrButtonEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description: MadvrButtonEntityDescription = description
        self._attr_unique_id = f"{coordinator.mac}_{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        await self.coordinator.client.add_command_to_queue(
            self.entity_description.command
        )
