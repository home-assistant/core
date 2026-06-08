"""Button platform for the OSRAM infrared integration."""

from dataclasses import dataclass

from infrared_protocols.codes.osram.light import OsramLightCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_ENTITY_ID
from .entity import OsramIrEmitterEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OsramIrButtonEntityDescription(ButtonEntityDescription):
    """Describe an OSRAM infrared button entity."""

    command_code: OsramLightCode


BUTTON_DESCRIPTIONS: tuple[OsramIrButtonEntityDescription, ...] = (
    OsramIrButtonEntityDescription(
        key="mode",
        translation_key="mode",
        command_code=OsramLightCode.MODE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OSRAM infrared buttons from a config entry."""
    if not (infrared_entity_id := entry.data.get(CONF_INFRARED_ENTITY_ID)):
        return

    async_add_entities(
        OsramIrButton(entry, infrared_entity_id, description)
        for description in BUTTON_DESCRIPTIONS
    )


class OsramIrButton(OsramIrEmitterEntity, ButtonEntity):
    """Representation of an OSRAM infrared remote button."""

    entity_description: OsramIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: OsramIrButtonEntityDescription,
    ) -> None:
        """Initialize an OSRAM infrared button."""
        super().__init__(
            entry,
            infrared_entity_id,
            unique_id_suffix=f"button_{description.key}",
        )
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the corresponding OSRAM infrared command."""
        await self._async_send_code(self.entity_description.command_code)
