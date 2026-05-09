"""Constants for the ADAM Audio integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "adam_audio"
MANUFACTURER = "ADAM Audio"

DEFAULT_PORT = 49494
SOCKET_TIMEOUT = 10.0

# How often HA polls the device for current state (reflects physical knob /
# A Control changes in HA).  Lower = more responsive, higher = less chatter.
POLL_INTERVAL = 15  # seconds
KEEPALIVE_TIMEOUT_SECS = 30  # OCA keepalive timeout we advertise to the device

SERVICE_TYPE = "_oca._udp.local."

# Backward-compat alias kept so nothing else needs changing.
KEEPALIVE_INTERVAL = POLL_INTERVAL

# ── Config entry keys ────────────────────────────────────────────────────────
CONF_HOST = "host"
CONF_PORT = "port"
CONF_DEVICE_NAME = "device_name"  # hardware name, e.g. "ASeries-41472b"
CONF_DESCRIPTION = "description"  # user-facing name, e.g. "Left"
CONF_SERIAL = "serial"

# ── Entity keys ──────────────────────────────────────────────────────────────
ENTITY_MUTE = "mute"
ENTITY_SLEEP = "sleep"
ENTITY_INPUT = "input_source"
ENTITY_VOICING = "voicing"
ENTITY_BASS = "bass"
ENTITY_DESK = "desk"
ENTITY_PRESENCE = "presence"
ENTITY_TREBLE = "treble"

# ── Group ────────────────────────────────────────────────────────────────────
GROUP_DEVICE_ID = "group_all_speakers"
GROUP_DEVICE_NAME = "All Speakers"

# ── Voicing ──────────────────────────────────────────────────────────────────
VOICING_OPTIONS = ["Pure", "UNR", "Ext"]
VOICING_TO_INT: dict[str, int] = {"Pure": 0, "UNR": 1, "Ext": 2}
VOICING_FROM_INT: dict[int, str] = {0: "Pure", 1: "UNR", 2: "Ext"}

# ── Input source ─────────────────────────────────────────────────────────────
INPUT_OPTIONS = ["RCA", "XLR"]
INPUT_TO_INT: dict[str, int] = {"RCA": 0, "XLR": 1}
INPUT_FROM_INT: dict[int, str] = {0: "RCA", 1: "XLR"}

# ── EQ ranges (direct integer values sent to device) ────────────────────────
BASS_MIN = -2
BASS_MAX = 1
DESK_MIN = -2
DESK_MAX = 0
PRESENCE_MIN = -1
PRESENCE_MAX = 1
TREBLE_MIN = -1
TREBLE_MAX = 1
EQ_STEP = 1
EQ_UNIT = ""
