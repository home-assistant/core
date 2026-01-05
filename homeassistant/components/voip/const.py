"""Constants for the Voice over IP integration."""

from typing import Final

DOMAIN = "voip"

RATE = 16000
WIDTH = 2
CHANNELS = 1
RTP_AUDIO_SETTINGS = {
    "rate": RATE,
    "width": WIDTH,
    "channels": CHANNELS,
    "sleep_ratio": 0.99,
}

CONF_SIP_PORT = "sip_port"
CONF_SIP_USER = "sip_user"

STORAGE_VER: Final = 1
