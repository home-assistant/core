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

CONF_SIP_PORT = "sip_port"

# Seconds of silence at the end of a voice command
SILENCE_DEFAULT = 1.0
SILENCE_RELAXED = 2.0
SILENCE_AGGRESSIVE = 0.5
