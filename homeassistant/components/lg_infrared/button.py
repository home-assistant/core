"""Button platform for LG IR integration."""

from __future__ import annotations

from dataclasses import dataclass

from infrared_protocols.codes.lg.tv import LGTVCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, LGDeviceType
from .entity import LgIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LgIrButtonEntityDescription(ButtonEntityDescription):
    """Describes LG IR button entity."""

    command_code: LGTVCode


TV_BUTTON_DESCRIPTIONS: tuple[LgIrButtonEntityDescription, ...] = (
    LgIrButtonEntityDescription(
        key="power_on", translation_key="power_on", command_code=LGTVCode.POWER_ON
    ),
    LgIrButtonEntityDescription(
        key="power_off", translation_key="power_off", command_code=LGTVCode.POWER_OFF
    ),
    LgIrButtonEntityDescription(
        key="hdmi_1", translation_key="hdmi_1", command_code=LGTVCode.HDMI_1
    ),
    LgIrButtonEntityDescription(
        key="hdmi_2", translation_key="hdmi_2", command_code=LGTVCode.HDMI_2
    ),
    LgIrButtonEntityDescription(
        key="hdmi_3", translation_key="hdmi_3", command_code=LGTVCode.HDMI_3
    ),
    LgIrButtonEntityDescription(
        key="hdmi_4", translation_key="hdmi_4", command_code=LGTVCode.HDMI_4
    ),
    LgIrButtonEntityDescription(
        key="exit", translation_key="exit", command_code=LGTVCode.EXIT
    ),
    LgIrButtonEntityDescription(
        key="info", translation_key="info", command_code=LGTVCode.INFO
    ),
    LgIrButtonEntityDescription(
        key="guide", translation_key="guide", command_code=LGTVCode.GUIDE
    ),
    LgIrButtonEntityDescription(
        key="up", translation_key="up", command_code=LGTVCode.NAV_UP
    ),
    LgIrButtonEntityDescription(
        key="down", translation_key="down", command_code=LGTVCode.NAV_DOWN
    ),
    LgIrButtonEntityDescription(
        key="left", translation_key="left", command_code=LGTVCode.NAV_LEFT
    ),
    LgIrButtonEntityDescription(
        key="right", translation_key="right", command_code=LGTVCode.NAV_RIGHT
    ),
    LgIrButtonEntityDescription(
        key="ok", translation_key="ok", command_code=LGTVCode.OK
    ),
    LgIrButtonEntityDescription(
        key="back", translation_key="back", command_code=LGTVCode.BACK
    ),
    LgIrButtonEntityDescription(
        key="home", translation_key="home", command_code=LGTVCode.HOME
    ),
    LgIrButtonEntityDescription(
        key="menu", translation_key="menu", command_code=LGTVCode.MENU
    ),
    LgIrButtonEntityDescription(
        key="input", translation_key="input", command_code=LGTVCode.INPUT
    ),
    LgIrButtonEntityDescription(
        key="num_0", translation_key="num_0", command_code=LGTVCode.NUM_0
    ),
    LgIrButtonEntityDescription(
        key="num_1", translation_key="num_1", command_code=LGTVCode.NUM_1
    ),
    LgIrButtonEntityDescription(
        key="num_2", translation_key="num_2", command_code=LGTVCode.NUM_2
    ),
    LgIrButtonEntityDescription(
        key="num_3", translation_key="num_3", command_code=LGTVCode.NUM_3
    ),
    LgIrButtonEntityDescription(
        key="num_4", translation_key="num_4", command_code=LGTVCode.NUM_4
    ),
    LgIrButtonEntityDescription(
        key="num_5", translation_key="num_5", command_code=LGTVCode.NUM_5
    ),
    LgIrButtonEntityDescription(
        key="num_6", translation_key="num_6", command_code=LGTVCode.NUM_6
    ),
    LgIrButtonEntityDescription(
        key="num_7", translation_key="num_7", command_code=LGTVCode.NUM_7
    ),
    LgIrButtonEntityDescription(
        key="num_8", translation_key="num_8", command_code=LGTVCode.NUM_8
    ),
    LgIrButtonEntityDescription(
        key="num_9", translation_key="num_9", command_code=LGTVCode.NUM_9
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG IR buttons from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    device_type = entry.data[CONF_DEVICE_TYPE]
    if device_type == LGDeviceType.TV:
        async_add_entities(
            LgIrButton(entry, infrared_entity_id, description)
            for description in TV_BUTTON_DESCRIPTIONS
        )


class LgIrButton(LgIrEntity, ButtonEntity):
    """LG IR button entity."""

    entity_description: LgIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: LgIrButtonEntityDescription,
    ) -> None:
        """Initialize LG IR button."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix=description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.command_code)
