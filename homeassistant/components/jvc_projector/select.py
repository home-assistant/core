"""Select platform for the jvc_projector integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from jvcprojector.projector import JvcProjector, const

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JvcProjectorSelectDescription(SelectEntityDescription):
    """Describes JVC Projector select entities."""

    command: Callable[[JvcProjector, str], Awaitable[None]]
    enabled_default: bool | Callable[[JvcProjectorEntity], bool] = True
    translation_key_override: str | None | Callable[[JvcProjectorEntity], str] = None


# type safe command function for a select
def create_select_command(key: str) -> Callable[[JvcProjector, str], Awaitable[None]]:
    """Create a command function for a select."""

    async def command(device: JvcProjector, option: str) -> None:
        await device.send_command(key, option)

    return command


# these options correspond to a command and its possible values
# note low latency is intentionally excluded because you can't just turn it on you need to meet conditions first so you should instead switch picture modes
JVC_SELECTS = (
    JvcProjectorSelectDescription(
        key=const.KEY_INPUT,
        translation_key=const.KEY_INPUT,
        options=const.VAL_FUNCTION_INPUT,
        command=create_select_command(const.KEY_INPUT),
    ),
    JvcProjectorSelectDescription(
        key=const.KEY_INSTALLATION_MODE,
        translation_key=const.KEY_INSTALLATION_MODE,
        options=const.VAL_INSTALLATION_MODE,
        command=create_select_command(const.KEY_INSTALLATION_MODE),
    ),
    JvcProjectorSelectDescription(
        key=const.KEY_ANAMORPHIC,
        translation_key=const.KEY_ANAMORPHIC,
        options=const.VAL_ANAMORPHIC,
        command=create_select_command(const.KEY_ANAMORPHIC),
    ),
    JvcProjectorSelectDescription(
        key=const.KEY_ESHIFT,
        translation_key=const.KEY_ESHIFT,
        options=const.VAL_TOGGLE,
        command=create_select_command(const.KEY_ESHIFT),
        enabled_default=JvcProjectorEntity.has_eshift,
    ),
    JvcProjectorSelectDescription(
        key=const.KEY_LASER_POWER,
        translation_key=const.KEY_LASER_POWER,
        translation_key_override=lambda entity: const.KEY_LASER_POWER
        if entity.has_laser
        else "lamp_power",
        options=const.VAL_LASER_POWER,
        command=create_select_command(const.KEY_LASER_POWER),
    ),
    JvcProjectorSelectDescription(
        key=const.KEY_LASER_DIMMING,
        translation_key=const.KEY_LASER_DIMMING,
        options=const.VAL_LASER_DIMMING,
        command=create_select_command(const.KEY_LASER_DIMMING),
        enabled_default=JvcProjectorEntity.has_laser,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JVCConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        JvcProjectorSelectEntity(coordinator, description)
        for description in JVC_SELECTS
    )


class JvcProjectorSelectEntity(JvcProjectorEntity, SelectEntity):
    """Representation of a JVC Projector select entity."""

    entity_description: JvcProjectorSelectDescription

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: JvcProjectorSelectDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_entity_registry_enabled_default = (
            description.enabled_default(self)
            if callable(description.enabled_default)
            else description.enabled_default
        )
        # allow for translation key override with callable
        self._attr_translation_key = (
            description.translation_key_override(self)
            if callable(description.translation_key_override)
            else description.translation_key_override
            if description.translation_key_override is not None
            else description.translation_key
        )

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.command(self.coordinator.device, option)
