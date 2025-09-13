# const.py
DOMAIN = "hegel"
DEFAULT_PORT = 50001

CONF_MODEL = "model"
CONF_MAX_VOLUME = "max_volume"  # 1.0 means amp’s internal max

# Very slow fallback poll (in seconds) as a safety net (1 hour)
SLOW_POLL_INTERVAL = 60 * 60

MODEL_INPUTS = {
    "Röst": [
        "Balanced", "Analog 1", "Analog 2", "Coaxial",
        "Optical 1", "Optical 2", "Optical 3", "USB", "Network"
    ],
    "H95": [
        "Analog 1", "Analog 2", "Coaxial",
        "Optical 1", "Optical 2", "Optical 3", "USB", "Network"
    ],
    "H120": [
        "Balanced", "Analog 1", "Analog 2", "Coaxial",
        "Optical 1", "Optical 2", "Optical 3", "USB", "Network"
    ],
    "H190": [
        "Balanced", "Analog 1", "Analog 2", "Coaxial",
        "Optical 1", "Optical 2", "Optical 3", "USB", "Network"
    ],
    "H190V": [
        "XLR", "Analog 1", "Analog 2", "Coaxial", "Optical 1",
        "Optical 2", "Optical 3", "USB", "Network", "Phono"
    ],
    "H390": [
        "XLR", "Analog 1", "Analog 2", "BNC", "Coaxial",
        "Optical 1", "Optical 2", "Optical 3", "USB", "Network"
    ],
    "H590": [
        "XLR 1", "XLR 2", "Analog 1", "Analog 2", "BNC",
        "Coaxial", "Optical 1", "Optical 2", "Optical 3", "USB", "Network"
    ],
}

# Centralized command strings
COMMANDS = {
    "power_on": "-p.1\r",
    "power_off": "-p.0\r",
    "power_query": "-p.?\r",
    "volume_set": lambda level: f"-v.{level}\r",  # 0..99
    "volume_query": "-v.?\r",
    "volume_up": "-v.u\r",
    "volume_down": "-v.d\r",
    "mute_on": "-m.1\r",
    "mute_off": "-m.0\r",
    "mute_query": "-m.?\r",
    "input_set": lambda idx: f"-i.{idx}\r",  # 1..9 (depends on model)
    "input_query": "-i.?\r",
    # reset/query if needed (some amps may expose this)
    "reset_query": "-r.?\r",
}
