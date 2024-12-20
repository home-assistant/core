"""Constants for the Voice over IP integration."""

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

DEFAULT_SIP_HOST = "127.0.0.1"

CONF_SIP_HOST = "sip_host"
CONF_SIP_PORT = "sip_port"
CONF_SIP_USER = "sip_user"
