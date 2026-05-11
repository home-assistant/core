"""Button platform for Samsung IR integration."""

from dataclasses import dataclass

from infrared_protocols.codes.samsung.tv import SamsungTVCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, SamsungDeviceType
from .entity import SamsungIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SamsungIrButtonEntityDescription(ButtonEntityDescription):
    """Describes Samsung IR button entity."""

    command_code: SamsungTVCode


TV_BUTTON_DESCRIPTIONS: tuple[SamsungIrButtonEntityDescription, ...] = (
    SamsungIrButtonEntityDescription(
        key="power", translation_key="power", command_code=SamsungTVCode.POWER
    ),
    SamsungIrButtonEntityDescription(
        key="hdmi_1", translation_key="hdmi_1", command_code=SamsungTVCode.HDMI_1
    ),
    SamsungIrButtonEntityDescription(
        key="hdmi_2", translation_key="hdmi_2", command_code=SamsungTVCode.HDMI_2
    ),
    SamsungIrButtonEntityDescription(
        key="hdmi_3", translation_key="hdmi_3", command_code=SamsungTVCode.HDMI_3
    ),
    SamsungIrButtonEntityDescription(
        key="hdmi_4", translation_key="hdmi_4", command_code=SamsungTVCode.HDMI_4
    ),
    SamsungIrButtonEntityDescription(
        key="exit", translation_key="exit", command_code=SamsungTVCode.EXIT
    ),
    SamsungIrButtonEntityDescription(
        key="info", translation_key="info", command_code=SamsungTVCode.INFO
    ),
    SamsungIrButtonEntityDescription(
        key="up", translation_key="up", command_code=SamsungTVCode.NAV_UP
    ),
    SamsungIrButtonEntityDescription(
        key="down", translation_key="down", command_code=SamsungTVCode.NAV_DOWN
    ),
    SamsungIrButtonEntityDescription(
        key="left", translation_key="left", command_code=SamsungTVCode.NAV_LEFT
    ),
    SamsungIrButtonEntityDescription(
        key="right", translation_key="right", command_code=SamsungTVCode.NAV_RIGHT
    ),
    SamsungIrButtonEntityDescription(
        key="ok", translation_key="ok", command_code=SamsungTVCode.OK
    ),
    SamsungIrButtonEntityDescription(
        key="return", translation_key="return", command_code=SamsungTVCode.RETURN
    ),
    SamsungIrButtonEntityDescription(
        key="home", translation_key="home", command_code=SamsungTVCode.HOME
    ),
    SamsungIrButtonEntityDescription(
        key="settings", translation_key="settings", command_code=SamsungTVCode.SETTINGS
    ),
    SamsungIrButtonEntityDescription(
        key="source", translation_key="source", command_code=SamsungTVCode.SOURCE
    ),
    SamsungIrButtonEntityDescription(
        key="num_0", translation_key="num_0", command_code=SamsungTVCode.NUM_0
    ),
    SamsungIrButtonEntityDescription(
        key="num_1", translation_key="num_1", command_code=SamsungTVCode.NUM_1
    ),
    SamsungIrButtonEntityDescription(
        key="num_2", translation_key="num_2", command_code=SamsungTVCode.NUM_2
    ),
    SamsungIrButtonEntityDescription(
        key="num_3", translation_key="num_3", command_code=SamsungTVCode.NUM_3
    ),
    SamsungIrButtonEntityDescription(
        key="num_4", translation_key="num_4", command_code=SamsungTVCode.NUM_4
    ),
    SamsungIrButtonEntityDescription(
        key="num_5", translation_key="num_5", command_code=SamsungTVCode.NUM_5
    ),
    SamsungIrButtonEntityDescription(
        key="num_6", translation_key="num_6", command_code=SamsungTVCode.NUM_6
    ),
    SamsungIrButtonEntityDescription(
        key="num_7", translation_key="num_7", command_code=SamsungTVCode.NUM_7
    ),
    SamsungIrButtonEntityDescription(
        key="num_8", translation_key="num_8", command_code=SamsungTVCode.NUM_8
    ),
    SamsungIrButtonEntityDescription(
        key="num_9", translation_key="num_9", command_code=SamsungTVCode.NUM_9
    ),
    SamsungIrButtonEntityDescription(
        key="red", translation_key="red", command_code=SamsungTVCode.RED
    ),
    SamsungIrButtonEntityDescription(
        key="green", translation_key="green", command_code=SamsungTVCode.GREEN
    ),
    SamsungIrButtonEntityDescription(
        key="yellow", translation_key="yellow", command_code=SamsungTVCode.YELLOW
    ),
    SamsungIrButtonEntityDescription(
        key="blue", translation_key="blue", command_code=SamsungTVCode.BLUE
    ),
    SamsungIrButtonEntityDescription(
        key="forward",
        translation_key="forward",
        command_code=SamsungTVCode.FAST_FORWARD,
    ),
    SamsungIrButtonEntityDescription(
        key="backward", translation_key="backward", command_code=SamsungTVCode.REWIND
    ),
    SamsungIrButtonEntityDescription(
        key="record", translation_key="record", command_code=SamsungTVCode.RECORD
    ),
    SamsungIrButtonEntityDescription(
        key="tools", translation_key="tools", command_code=SamsungTVCode.TOOLS
    ),
    SamsungIrButtonEntityDescription(
        key="browser", translation_key="browser", command_code=SamsungTVCode.BROWSER
    ),
    SamsungIrButtonEntityDescription(
        key="tv_button", translation_key="tv", command_code=SamsungTVCode.TV
    ),
    SamsungIrButtonEntityDescription(
        key="previous_channel",
        translation_key="previous_channel",
        command_code=SamsungTVCode.PREVIOUS_CHANNEL,
    ),
    SamsungIrButtonEntityDescription(
        key="subtitle",
        translation_key="subtitle",
        command_code=SamsungTVCode.AD_SUBTITLE,
    ),
    SamsungIrButtonEntityDescription(
        key="e_manual",
        translation_key="e_manual",
        command_code=SamsungTVCode.E_MANUAL,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Samsung IR buttons from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    device_type = entry.data[CONF_DEVICE_TYPE]
    if device_type == SamsungDeviceType.TV:
        async_add_entities(
            SamsungIrButton(entry, infrared_entity_id, description)
            for description in TV_BUTTON_DESCRIPTIONS
        )


class SamsungIrButton(SamsungIrEntity, ButtonEntity):
    """Samsung IR button entity."""

    entity_description: SamsungIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: SamsungIrButtonEntityDescription,
    ) -> None:
        """Initialize Samsung IR button."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix=description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.command_code)
