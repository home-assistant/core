"""Codeset and entity descriptions for LG IR integration."""
from dataclasses import dataclass
from enum import Enum

from infrared_protocols.codes.lg.tv import LGTVCode, LGTVCodeJP
from homeassistant.components.button import ButtonEntityDescription

@dataclass(frozen=True, kw_only=True)
class LgIrButtonEntityDescription(ButtonEntityDescription):
    """Describes LG IR button entity."""

    command_code: Enum


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
        key="aspect", translation_key="aspect", command_code=LGTVCode.ASPECT
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
        key="settings", translation_key="settings", command_code=LGTVCode.SETTINGS
    ),
    LgIrButtonEntityDescription(
        key="list", translation_key="list", command_code=LGTVCode.LIST
    ),
    LgIrButtonEntityDescription(
        key="text", translation_key="text", command_code=LGTVCode.TEXT
    ),
    LgIrButtonEntityDescription(
        key="yellow", translation_key="yellow", command_code=LGTVCode.YELLOW
    ),
    LgIrButtonEntityDescription(
        key="green", translation_key="green", command_code=LGTVCode.GREEN
    ),
    LgIrButtonEntityDescription(
        key="red", translation_key="red", command_code=LGTVCode.RED
    ),
    LgIrButtonEntityDescription(
        key="blue", translation_key="blue", command_code=LGTVCode.BLUE
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
    LgIrButtonEntityDescription(
        key="channel_up", translation_key="channel_up", command_code=LGTVCode.CHANNEL_UP
    ),
    LgIrButtonEntityDescription(
        key="channel_down", translation_key="channel_down", command_code=LGTVCode.CHANNEL_DOWN
    ),
    LgIrButtonEntityDescription(
        key="volume_up", translation_key="volume_up", command_code=LGTVCode.VOLUME_UP
    ),
    LgIrButtonEntityDescription(
        key="volume_down", translation_key="volume_down", command_code=LGTVCode.VOLUME_DOWN
    ),
    LgIrButtonEntityDescription(
        key="mute", translation_key="mute", command_code=LGTVCode.MUTE
    ),
    LgIrButtonEntityDescription(
        key="sap", translation_key="sap", command_code=LGTVCode.SAP
    ),
    LgIrButtonEntityDescription(
        key="subtitle", translation_key="subtitle", command_code=LGTVCode.SUBTITLE
    ),
)

TV_JAPAN_BUTTON_DESCRIPTIONS: tuple[LgIrButtonEntityDescription, ...] = (
    LgIrButtonEntityDescription(
        key="power", translation_key="power", command_code=LGTVCodeJP.POWER
    ),
    LgIrButtonEntityDescription(
        key="power_on", translation_key="power_on", command_code=LGTVCodeJP.POWER_ON
    ),
    LgIrButtonEntityDescription(
        key="power_off", translation_key="power_off", command_code=LGTVCodeJP.POWER_OFF
    ),
    LgIrButtonEntityDescription(
        key="tv", translation_key="tv", command_code=LGTVCodeJP.TV
    ),
    LgIrButtonEntityDescription(
        key="dtv", translation_key="dtv", command_code=LGTVCodeJP.DTV
    ),
    LgIrButtonEntityDescription(
        key="bs", translation_key="bs", command_code=LGTVCodeJP.BS
    ),
    LgIrButtonEntityDescription(
        key="cs", translation_key="cs", command_code=LGTVCodeJP.CS
    ),
    LgIrButtonEntityDescription(
        key="hdmi_1", translation_key="hdmi_1", command_code=LGTVCodeJP.HDMI_1
    ),
    LgIrButtonEntityDescription(
        key="hdmi_2", translation_key="hdmi_2", command_code=LGTVCodeJP.HDMI_2
    ),
    LgIrButtonEntityDescription(
        key="hdmi_3", translation_key="hdmi_3", command_code=LGTVCodeJP.HDMI_3
    ),
    LgIrButtonEntityDescription(
        key="hdmi_4", translation_key="hdmi_4", command_code=LGTVCodeJP.HDMI_4
    ),
    LgIrButtonEntityDescription(
        key="aspect", translation_key="aspect", command_code=LGTVCodeJP.ASPECT
    ),
    LgIrButtonEntityDescription(
        key="exit", translation_key="exit", command_code=LGTVCodeJP.EXIT
    ),
    LgIrButtonEntityDescription(
        key="info", translation_key="info", command_code=LGTVCodeJP.INFO
    ),
    LgIrButtonEntityDescription(
        key="guide", translation_key="guide", command_code=LGTVCodeJP.GUIDE
    ),
    LgIrButtonEntityDescription(
        key="settings", translation_key="settings", command_code=LGTVCodeJP.SETTINGS
    ),
    LgIrButtonEntityDescription(
        key="list", translation_key="list", command_code=LGTVCodeJP.LIST
    ),
    LgIrButtonEntityDescription(
        key="data", translation_key="data", command_code=LGTVCodeJP.DATA
    ),
    LgIrButtonEntityDescription(
        key="yellow", translation_key="yellow", command_code=LGTVCodeJP.YELLOW
    ),
    LgIrButtonEntityDescription(
        key="green", translation_key="green", command_code=LGTVCodeJP.GREEN
    ),
    LgIrButtonEntityDescription(
        key="red", translation_key="red", command_code=LGTVCodeJP.RED
    ),
    LgIrButtonEntityDescription(
        key="blue", translation_key="blue", command_code=LGTVCodeJP.BLUE
    ),
    LgIrButtonEntityDescription(
        key="up", translation_key="up", command_code=LGTVCodeJP.NAV_UP
    ),
    LgIrButtonEntityDescription(
        key="down", translation_key="down", command_code=LGTVCodeJP.NAV_DOWN
    ),
    LgIrButtonEntityDescription(
        key="left", translation_key="left", command_code=LGTVCodeJP.NAV_LEFT
    ),
    LgIrButtonEntityDescription(
        key="right", translation_key="right", command_code=LGTVCodeJP.NAV_RIGHT
    ),
    LgIrButtonEntityDescription(
        key="ok", translation_key="ok", command_code=LGTVCodeJP.OK
    ),
    LgIrButtonEntityDescription(
        key="back", translation_key="back", command_code=LGTVCodeJP.BACK
    ),
    LgIrButtonEntityDescription(
        key="home", translation_key="home", command_code=LGTVCodeJP.HOME
    ),
    LgIrButtonEntityDescription(
        key="menu", translation_key="menu", command_code=LGTVCodeJP.MENU
    ),
    LgIrButtonEntityDescription(
        key="input", translation_key="input", command_code=LGTVCodeJP.INPUT
    ),
    LgIrButtonEntityDescription(
        key="num_1", translation_key="num_1", command_code=LGTVCodeJP.NUM_1
    ),
    LgIrButtonEntityDescription(
        key="num_2", translation_key="num_2", command_code=LGTVCodeJP.NUM_2
    ),
    LgIrButtonEntityDescription(
        key="num_3", translation_key="num_3", command_code=LGTVCodeJP.NUM_3
    ),
    LgIrButtonEntityDescription(
        key="num_4", translation_key="num_4", command_code=LGTVCodeJP.NUM_4
    ),
    LgIrButtonEntityDescription(
        key="num_5", translation_key="num_5", command_code=LGTVCodeJP.NUM_5
    ),
    LgIrButtonEntityDescription(
        key="num_6", translation_key="num_6", command_code=LGTVCodeJP.NUM_6
    ),
    LgIrButtonEntityDescription(
        key="num_7", translation_key="num_7", command_code=LGTVCodeJP.NUM_7
    ),
    LgIrButtonEntityDescription(
        key="num_8", translation_key="num_8", command_code=LGTVCodeJP.NUM_8
    ),
    LgIrButtonEntityDescription(
        key="num_9", translation_key="num_9", command_code=LGTVCodeJP.NUM_9
    ),
    LgIrButtonEntityDescription(
        key="num_10", translation_key="num_10", command_code=LGTVCodeJP.NUM_10
    ),
    LgIrButtonEntityDescription(
        key="num_11", translation_key="num_11", command_code=LGTVCodeJP.NUM_11
    ),
    LgIrButtonEntityDescription(
        key="num_12", translation_key="num_12", command_code=LGTVCodeJP.NUM_12
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_1", translation_key="dtv_num_1", command_code=LGTVCodeJP.DTV_NUM_1
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_2", translation_key="dtv_num_2", command_code=LGTVCodeJP.DTV_NUM_2
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_3", translation_key="dtv_num_3", command_code=LGTVCodeJP.DTV_NUM_3
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_4", translation_key="dtv_num_4", command_code=LGTVCodeJP.DTV_NUM_4
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_5", translation_key="dtv_num_5", command_code=LGTVCodeJP.DTV_NUM_5
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_6", translation_key="dtv_num_6", command_code=LGTVCodeJP.DTV_NUM_6
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_7", translation_key="dtv_num_7", command_code=LGTVCodeJP.DTV_NUM_7
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_8", translation_key="dtv_num_8", command_code=LGTVCodeJP.DTV_NUM_8
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_9", translation_key="dtv_num_9", command_code=LGTVCodeJP.DTV_NUM_9
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_10", translation_key="dtv_num_10", command_code=LGTVCodeJP.DTV_NUM_10
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_11", translation_key="dtv_num_11", command_code=LGTVCodeJP.DTV_NUM_11
    ),
    LgIrButtonEntityDescription(
        key="dtv_num_12", translation_key="dtv_num_12", command_code=LGTVCodeJP.DTV_NUM_12
    ),
    LgIrButtonEntityDescription(
        key="bs_num_1", translation_key="bs_num_1", command_code=LGTVCodeJP.BS_NUM_1
    ),
    LgIrButtonEntityDescription(
        key="bs_num_2", translation_key="bs_num_2", command_code=LGTVCodeJP.BS_NUM_2
    ),
    LgIrButtonEntityDescription(
        key="bs_num_3", translation_key="bs_num_3", command_code=LGTVCodeJP.BS_NUM_3
    ),
    LgIrButtonEntityDescription(
        key="bs_num_4", translation_key="bs_num_4", command_code=LGTVCodeJP.BS_NUM_4
    ),
    LgIrButtonEntityDescription(
        key="bs_num_5", translation_key="bs_num_5", command_code=LGTVCodeJP.BS_NUM_5
    ),
    LgIrButtonEntityDescription(
        key="bs_num_6", translation_key="bs_num_6", command_code=LGTVCodeJP.BS_NUM_6
    ),
    LgIrButtonEntityDescription(
        key="bs_num_7", translation_key="bs_num_7", command_code=LGTVCodeJP.BS_NUM_7
    ),
    LgIrButtonEntityDescription(
        key="bs_num_8", translation_key="bs_num_8", command_code=LGTVCodeJP.BS_NUM_8
    ),
    LgIrButtonEntityDescription(
        key="bs_num_9", translation_key="bs_num_9", command_code=LGTVCodeJP.BS_NUM_9
    ),
    LgIrButtonEntityDescription(
        key="bs_num_10", translation_key="bs_num_10", command_code=LGTVCodeJP.BS_NUM_10
    ),
    LgIrButtonEntityDescription(
        key="bs_num_11", translation_key="bs_num_11", command_code=LGTVCodeJP.BS_NUM_11
    ),
    LgIrButtonEntityDescription(
        key="bs_num_12", translation_key="bs_num_12", command_code=LGTVCodeJP.BS_NUM_12
    ),
    LgIrButtonEntityDescription(
        key="cs_num_1", translation_key="cs_num_1", command_code=LGTVCodeJP.CS_NUM_1
    ),
    LgIrButtonEntityDescription(
        key="cs_num_2", translation_key="cs_num_2", command_code=LGTVCodeJP.CS_NUM_2
    ),
    LgIrButtonEntityDescription(
        key="cs_num_3", translation_key="cs_num_3", command_code=LGTVCodeJP.CS_NUM_3
    ),
    LgIrButtonEntityDescription(
        key="cs_num_4", translation_key="cs_num_4", command_code=LGTVCodeJP.CS_NUM_4
    ),
    LgIrButtonEntityDescription(
        key="cs_num_5", translation_key="cs_num_5", command_code=LGTVCodeJP.CS_NUM_5
    ),
    LgIrButtonEntityDescription(
        key="cs_num_6", translation_key="cs_num_6", command_code=LGTVCodeJP.CS_NUM_6
    ),
    LgIrButtonEntityDescription(
        key="cs_num_7", translation_key="cs_num_7", command_code=LGTVCodeJP.CS_NUM_7
    ),
    LgIrButtonEntityDescription(
        key="cs_num_8", translation_key="cs_num_8", command_code=LGTVCodeJP.CS_NUM_8
    ),
    LgIrButtonEntityDescription(
        key="cs_num_9", translation_key="cs_num_9", command_code=LGTVCodeJP.CS_NUM_9
    ),
    LgIrButtonEntityDescription(
        key="cs_num_10", translation_key="cs_num_10", command_code=LGTVCodeJP.CS_NUM_10
    ),
    LgIrButtonEntityDescription(
        key="cs_num_11", translation_key="cs_num_11", command_code=LGTVCodeJP.CS_NUM_11
    ),
    LgIrButtonEntityDescription(
        key="cs_num_12", translation_key="cs_num_12", command_code=LGTVCodeJP.CS_NUM_12
    ),
    LgIrButtonEntityDescription(
        key="channel_up", translation_key="channel_up", command_code=LGTVCodeJP.CHANNEL_UP
    ),
    LgIrButtonEntityDescription(
        key="channel_down", translation_key="channel_down", command_code=LGTVCodeJP.CHANNEL_DOWN
    ),
    LgIrButtonEntityDescription(
        key="volume_up", translation_key="volume_up", command_code=LGTVCodeJP.VOLUME_UP
    ),
    LgIrButtonEntityDescription(
        key="volume_down", translation_key="volume_down", command_code=LGTVCodeJP.VOLUME_DOWN
    ),
    LgIrButtonEntityDescription(
        key="mute", translation_key="mute", command_code=LGTVCodeJP.MUTE
    ),
    LgIrButtonEntityDescription(
        key="sap", translation_key="sap", command_code=LGTVCodeJP.SAP
    ),
    LgIrButtonEntityDescription(
        key="subtitle", translation_key="subtitle", command_code=LGTVCodeJP.SUBTITLE
    ),
    LgIrButtonEntityDescription(
        key="record", translation_key="record", command_code=LGTVCodeJP.RECORD
    ),
    LgIrButtonEntityDescription(
        key="rec_list", translation_key="rec_list", command_code=LGTVCodeJP.REC_LIST
    ),
    
)

@dataclass(frozen=True)
class LGCodeset:
    key: str
    name: str
    codes: type[Enum]
    buttons: tuple[LgIrButtonEntityDescription, ...]
    has_tuner: bool = False
    tuner_options: list[str] | None = None

LG_CODESETS: dict[str, LGCodeset] = {
    "global": LGCodeset(
        key="global",
        name="Global",
        codes=LGTVCode,
        buttons=TV_BUTTON_DESCRIPTIONS,
    ),
    "japan": LGCodeset(
        key="japan",
        name="Japan",
        codes=LGTVCodeJP,
        buttons=TV_JAPAN_BUTTON_DESCRIPTIONS,
        has_tuner=True,
        tuner_options=["DTV", "BS", "CS"],
    ),
}
