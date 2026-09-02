"""Constants for the Wibeee integration."""

from datetime import timedelta

DOMAIN = "wibeee"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONF_MAC_ADDRESS = "mac_address"
CONF_WIBEEE_ID = "wibeee_id"

PHASE_PREFIXES: dict[str, str] = {
    "fase1": "l1",
    "fase2": "l2",
    "fase3": "l3",
    "fase4": "total",
}

KNOWN_MODELS = {
    "WBM": "Wibeee 1Ph",
    "WBT": "Wibeee 3Ph",
    "WMX": "Wibeee MAX",
    "WTD": "Wibeee 3Ph RN",
    "WX2": "Wibeee MAX 2S",
    "WX3": "Wibeee MAX 3S",
    "WXX": "Wibeee MAX MS",
    "WBB": "Wibeee BOX",
    "WB3": "Wibeee BOX S3P",
    "W3P": "Wibeee 3Ph 3W",
    "WGD": "Wibeee GND",
    "WBP": "Wibeee SMART PLUG",
}
