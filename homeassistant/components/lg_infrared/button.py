"""Button platform for LG IR integration."""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.lg.ac import LGACCode
from infrared_protocols.codes.lg.home_theater import LGHomeTheaterCode
from infrared_protocols.codes.lg.tv import LGTVCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, LGDeviceType
from .entity import LgIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LgIrButtonEntityDescription(ButtonEntityDescription):
    """Describes LG IR button entity."""

    command_code: LGTVCode | LGACCode | LGHomeTheaterCode


TV_BUTTON_DESCRIPTIONS: tuple[LgIrButtonEntityDescription, ...] = (
    LgIrButtonEntityDescription(
        key="power", translation_key="power", command_code=LGTVCode.POWER
    ),
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

# One-shot AC actions with no discrete on/off code, so each is a momentary button.
AC_BUTTON_DESCRIPTIONS: tuple[LgIrButtonEntityDescription, ...] = (
    LgIrButtonEntityDescription(
        key="jet", translation_key="jet", command_code=LGACCode.JET
    ),
    LgIrButtonEntityDescription(
        key="eco", translation_key="eco", command_code=LGACCode.ECO
    ),
    # A separate boost from JET, only offered on LG India units, so it is
    # disabled by default.
    LgIrButtonEntityDescription(
        key="viraat",
        translation_key="viraat",
        command_code=LGACCode.VIRAAT,
        entity_registry_enabled_default=False,
    ),
    LgIrButtonEntityDescription(
        key="ai_convertible",
        translation_key="ai_convertible",
        command_code=LGACCode.AI_CONVERTIBLE,
    ),
    LgIrButtonEntityDescription(
        key="light",
        translation_key="light",
        command_code=LGACCode.LIGHT_TOGGLE,
        entity_category=EntityCategory.CONFIG,
    ),
    LgIrButtonEntityDescription(
        key="wifi",
        translation_key="wifi",
        command_code=LGACCode.WIFI_TOGGLE,
        entity_category=EntityCategory.CONFIG,
    ),
    LgIrButtonEntityDescription(
        key="audio",
        translation_key="audio",
        command_code=LGACCode.AUDIO_TOGGLE,
        entity_category=EntityCategory.CONFIG,
    ),
    LgIrButtonEntityDescription(
        key="diagnose",
        translation_key="diagnose",
        command_code=LGACCode.DIAGNOSE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Only flips between auto-swing and off; the climate swing dropdown supersedes it,
    # so it is kept for older units but disabled by default.
    LgIrButtonEntityDescription(
        key="swing_v_toggle",
        translation_key="swing_v_toggle",
        command_code=LGACCode.SWING_V_TOGGLE,
        entity_registry_enabled_default=False,
    ),
)

HOME_THEATER_BUTTON_DESCRIPTIONS: tuple[LgIrButtonEntityDescription, ...] = (
    LgIrButtonEntityDescription(
        key="power", translation_key="power", command_code=LGHomeTheaterCode.POWER
    ),
    LgIrButtonEntityDescription(
        key="home", translation_key="home", command_code=LGHomeTheaterCode.HOME
    ),
    LgIrButtonEntityDescription(
        key="input",
        translation_key="input",
        command_code=LGHomeTheaterCode.FUNCTION,
    ),
    LgIrButtonEntityDescription(
        key="info",
        translation_key="info",
        command_code=LGHomeTheaterCode.INFO_MENU,
    ),
    LgIrButtonEntityDescription(
        key="disc_menu",
        translation_key="disc_menu",
        command_code=LGHomeTheaterCode.DISC_MENU,
    ),
    LgIrButtonEntityDescription(
        key="title_popup",
        translation_key="title_popup",
        command_code=LGHomeTheaterCode.TITLE_POPUP,
    ),
    LgIrButtonEntityDescription(
        key="up", translation_key="up", command_code=LGHomeTheaterCode.NAV_UP
    ),
    LgIrButtonEntityDescription(
        key="down", translation_key="down", command_code=LGHomeTheaterCode.NAV_DOWN
    ),
    LgIrButtonEntityDescription(
        key="left", translation_key="left", command_code=LGHomeTheaterCode.NAV_LEFT
    ),
    LgIrButtonEntityDescription(
        key="right", translation_key="right", command_code=LGHomeTheaterCode.NAV_RIGHT
    ),
    LgIrButtonEntityDescription(
        key="ok", translation_key="ok", command_code=LGHomeTheaterCode.OK
    ),
    LgIrButtonEntityDescription(
        key="back", translation_key="back", command_code=LGHomeTheaterCode.BACK
    ),
    LgIrButtonEntityDescription(
        key="clear", translation_key="clear", command_code=LGHomeTheaterCode.CLEAR
    ),
    LgIrButtonEntityDescription(
        key="num_0", translation_key="num_0", command_code=LGHomeTheaterCode.NUM_0
    ),
    LgIrButtonEntityDescription(
        key="num_1", translation_key="num_1", command_code=LGHomeTheaterCode.NUM_1
    ),
    LgIrButtonEntityDescription(
        key="num_2", translation_key="num_2", command_code=LGHomeTheaterCode.NUM_2
    ),
    LgIrButtonEntityDescription(
        key="num_3", translation_key="num_3", command_code=LGHomeTheaterCode.NUM_3
    ),
    LgIrButtonEntityDescription(
        key="num_4", translation_key="num_4", command_code=LGHomeTheaterCode.NUM_4
    ),
    LgIrButtonEntityDescription(
        key="num_5", translation_key="num_5", command_code=LGHomeTheaterCode.NUM_5
    ),
    LgIrButtonEntityDescription(
        key="num_6", translation_key="num_6", command_code=LGHomeTheaterCode.NUM_6
    ),
    LgIrButtonEntityDescription(
        key="num_7", translation_key="num_7", command_code=LGHomeTheaterCode.NUM_7
    ),
    LgIrButtonEntityDescription(
        key="num_8", translation_key="num_8", command_code=LGHomeTheaterCode.NUM_8
    ),
    LgIrButtonEntityDescription(
        key="num_9", translation_key="num_9", command_code=LGHomeTheaterCode.NUM_9
    ),
    LgIrButtonEntityDescription(
        key="asterisk",
        translation_key="asterisk",
        command_code=LGHomeTheaterCode.ASTERISK,
    ),
    LgIrButtonEntityDescription(
        key="open_close",
        translation_key="open_close",
        command_code=LGHomeTheaterCode.OPEN_CLOSE,
    ),
    LgIrButtonEntityDescription(
        key="optical_tv_sound",
        translation_key="optical_tv_sound",
        command_code=LGHomeTheaterCode.OPTICAL_TV_SOUND,
    ),
    LgIrButtonEntityDescription(
        key="sound_effect",
        translation_key="sound_effect",
        command_code=LGHomeTheaterCode.SOUND_EFFECT,
    ),
    LgIrButtonEntityDescription(
        key="speaker_level",
        translation_key="speaker_level",
        command_code=LGHomeTheaterCode.SPEAKER_LEVEL,
    ),
    LgIrButtonEntityDescription(
        key="audio_track",
        translation_key="audio_track",
        command_code=LGHomeTheaterCode.AUDIO,
    ),
    LgIrButtonEntityDescription(
        key="subtitle",
        translation_key="subtitle",
        command_code=LGHomeTheaterCode.SUBTITLE,
    ),
    LgIrButtonEntityDescription(
        key="sleep", translation_key="sleep", command_code=LGHomeTheaterCode.SLEEP
    ),
    LgIrButtonEntityDescription(
        key="record", translation_key="record", command_code=LGHomeTheaterCode.RECORD
    ),
    LgIrButtonEntityDescription(
        key="repeat", translation_key="repeat", command_code=LGHomeTheaterCode.REPEAT
    ),
    LgIrButtonEntityDescription(
        key="rewind",
        translation_key="rewind",
        command_code=LGHomeTheaterCode.SCAN_BACKWARD,
    ),
    LgIrButtonEntityDescription(
        key="fast_forward",
        translation_key="fast_forward",
        command_code=LGHomeTheaterCode.SCAN_FORWARD,
    ),
    LgIrButtonEntityDescription(
        key="red", translation_key="red", command_code=LGHomeTheaterCode.RED
    ),
    LgIrButtonEntityDescription(
        key="green", translation_key="green", command_code=LGHomeTheaterCode.GREEN
    ),
    LgIrButtonEntityDescription(
        key="yellow", translation_key="yellow", command_code=LGHomeTheaterCode.YELLOW
    ),
    LgIrButtonEntityDescription(
        key="blue", translation_key="blue", command_code=LGHomeTheaterCode.BLUE
    ),
)

_DEVICE_BUTTONS: dict[LGDeviceType, tuple[LgIrButtonEntityDescription, ...]] = {
    LGDeviceType.TV: TV_BUTTON_DESCRIPTIONS,
    LGDeviceType.AC: AC_BUTTON_DESCRIPTIONS,
    LGDeviceType.HOME_THEATER: HOME_THEATER_BUTTON_DESCRIPTIONS,
}
_DEVICE_NAMES: dict[LGDeviceType, str] = {
    LGDeviceType.TV: "LG TV",
    LGDeviceType.AC: "LG AC",
    LGDeviceType.HOME_THEATER: "LG Home Theater",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG IR buttons from config entry."""
    if not (infrared_entity_id := entry.data.get(CONF_INFRARED_ENTITY_ID)):
        return

    device_type = entry.data[CONF_DEVICE_TYPE]
    device_name = _DEVICE_NAMES[device_type]
    async_add_entities(
        LgIrButton(entry, infrared_entity_id, description, device_name)
        for description in _DEVICE_BUTTONS[device_type]
    )


class LgIrButton(LgIrEntity, InfraredEmitterConsumerEntity, ButtonEntity):
    """LG IR button entity."""

    entity_description: LgIrButtonEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        description: LgIrButtonEntityDescription,
        device_name: str,
    ) -> None:
        """Initialize LG IR button."""
        super().__init__(
            entry, unique_id_suffix=description.key, device_name=device_name
        )
        self._infrared_emitter_entity_id = infrared_entity_id
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self.entity_description.command_code.to_command())
