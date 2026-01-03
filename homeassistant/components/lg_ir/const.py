"""Constants for the LG IR integration."""

DOMAIN = "lg_ir"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"

LG_ADDRESS = 0xFB04


class LGCommand:
    """LG TV IR command codes."""

    BACK = 0xD728
    CHANNEL_DOWN = 0xFE01
    CHANNEL_UP = 0xFF00
    EXIT = 0xA45B
    FAST_FORWARD = 0x718E
    GUIDE = 0x56A9
    HDMI_1 = 0x31CE
    HDMI_2 = 0x33CC
    HDMI_3 = 0x16E9
    HDMI_4 = 0x25DA
    HOME = 0x837C
    INFO = 0x55AA
    INPUT = 0xF40B
    MENU = 0xBC43
    MUTE = 0xF609
    NAV_DOWN = 0xBE41
    NAV_LEFT = 0xF807
    NAV_RIGHT = 0xF906
    NAV_UP = 0xBF40
    NUM_0 = 0xEF10
    NUM_1 = 0xEE11
    NUM_2 = 0xED12
    NUM_3 = 0xEC13
    NUM_4 = 0xEB14
    NUM_5 = 0xEA15
    NUM_6 = 0xE916
    NUM_7 = 0xE817
    NUM_8 = 0xE718
    NUM_9 = 0xE619
    OK = 0xBB44
    PAUSE = 0x45BA
    PLAY = 0x4FB0
    POWER = 0xF708
    POWER_ON = 0x3BC4
    POWER_OFF = 0x3AC5
    REWIND = 0x708F
    STOP = 0x4EB1
    VOLUME_DOWN = 0xFC03
    VOLUME_UP = 0xFD02
