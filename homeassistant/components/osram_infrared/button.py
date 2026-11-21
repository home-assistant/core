"""Buttons for the OSRAM infrared remote control."""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.osram.light import OsramLightCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_IR_EMITTER_ENTITY_ID
from .entity import OsramIrEmitterEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OsramIrButtonEntityDescription(ButtonEntityDescription):
    """Describe an OSRAM remote button and its infrared command."""

    code: OsramLightCode


BUTTON_DESCRIPTIONS: tuple[OsramIrButtonEntityDescription, ...] = tuple(
    OsramIrButtonEntityDescription(
        key=code.name.lower(),
        translation_key=code.name.lower(),
        code=code,
        entity_registry_enabled_default=code
        in {
            OsramLightCode.BRIGHTNESS_UP,
            OsramLightCode.BRIGHTNESS_DOWN,
        },
    )
    for code in OsramLightCode
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all physical remote buttons for an OSRAM infrared light."""
    async_add_entities(
        OsramIrButton(entry, entry.data[CONF_IR_EMITTER_ENTITY_ID], description)
        for description in BUTTON_DESCRIPTIONS
    )


class OsramIrButton(OsramIrEmitterEntity, ButtonEntity):
    """An OSRAM infrared remote button."""

    entity_description: OsramIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        emitter_entity_id: str,
        description: OsramIrButtonEntityDescription,
    ) -> None:
        """Initialize an OSRAM remote button."""
        super().__init__(entry, emitter_entity_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @override
    async def async_press(self) -> None:
        """Send the remote command without changing the light's assumed state."""
        await self._async_send_code(self.entity_description.code)
