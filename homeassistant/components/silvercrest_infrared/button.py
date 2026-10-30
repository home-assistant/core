"""Button platform for SilverCrest Infrared integration."""

from dataclasses import dataclass
from enum import StrEnum
from typing import override

from infrared_protocols.codes.silvercrest.fan import SilverCrestFanCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DEVICE_NAMES,
    DOMAIN,
    MISTING_FANS,
)

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class SilverCrestIrButtonEntityDescription(ButtonEntityDescription):
    """SilverCrest Infrared Button Description."""

    code: SilverCrestFanCode


class SilverCrestIrbutton(StrEnum):
    """SilverCrest buttons."""

    POWER = "power"
    SPEED = "speed"
    TIMER = "timer"
    OSC = "osc"
    MODE = "mode"
    MIST = "mist"


BUTTON_DESCRIPTIONS: tuple[SilverCrestIrButtonEntityDescription, ...] = (
    SilverCrestIrButtonEntityDescription(
        key=SilverCrestIrbutton.POWER,
        translation_key=SilverCrestIrbutton.POWER,
        code=SilverCrestFanCode.POWER,
    ),
    SilverCrestIrButtonEntityDescription(
        key=SilverCrestIrbutton.SPEED,
        translation_key=SilverCrestIrbutton.SPEED,
        code=SilverCrestFanCode.SPEED,
    ),
    SilverCrestIrButtonEntityDescription(
        key=SilverCrestIrbutton.TIMER,
        translation_key=SilverCrestIrbutton.TIMER,
        code=SilverCrestFanCode.TIMER,
    ),
    SilverCrestIrButtonEntityDescription(
        key=SilverCrestIrbutton.OSC,
        translation_key=SilverCrestIrbutton.OSC,
        code=SilverCrestFanCode.OSC,
    ),
)

MIST_BUTTON_DESCRIPTION = SilverCrestIrButtonEntityDescription(
    key=SilverCrestIrbutton.MIST,
    translation_key=SilverCrestIrbutton.MIST,
    code=SilverCrestFanCode.MODE,
)
MODE_BUTTON_DESCRIPTION = SilverCrestIrButtonEntityDescription(
    key=SilverCrestIrbutton.MODE,
    translation_key=SilverCrestIrbutton.MODE,
    code=SilverCrestFanCode.MODE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up platform from config entry."""
    if not (infrared_entity_id := entry.data.get(CONF_INFRARED_ENTITY_ID)):
        return

    async_add_entities(
        [
            SilverCrestIrButtonEntity(entry, infrared_entity_id, description)
            for description in (
                *BUTTON_DESCRIPTIONS,
                MIST_BUTTON_DESCRIPTION
                if entry.data[CONF_DEVICE_TYPE] in MISTING_FANS
                else MODE_BUTTON_DESCRIPTION,
            )
        ]
    )


class SilverCrestIrButtonEntity(InfraredEmitterConsumerEntity, ButtonEntity):
    """Represents a SilverCrest Infrared button entity."""

    entity_description: SilverCrestIrButtonEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: SilverCrestIrButtonEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self._infrared_emitter_entity_id = infrared_entity_id
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="SilverCrest",
            translation_key=entry.data[CONF_DEVICE_TYPE],
            model=DEVICE_NAMES[entry.data[CONF_DEVICE_TYPE]],
        )

        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.code.to_command())
