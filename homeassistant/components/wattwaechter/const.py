"""Constants for the WattWächter integration."""

DOMAIN = "wattwaechter"

DEFAULT_SCAN_INTERVAL = 120

CONF_FW_VERSION = "fw_version"

MANUFACTURER = "SmartCircuits GmbH"

MODEL_ID_PLUS = "ww_plus"

# Product names by model ID, used when the firmware does not report a
# product name (older firmware) or system info is unavailable.
MODEL_NAMES: dict[str, str] = {
    MODEL_ID_PLUS: "WattWächter Plus",
    "ww_gw_mf": "WattWächter Gas/Wasser",
    "ww_gw_id": "WattWächter Gas/Wasser",
}

# Model IDs for the mDNS model TXT record, which earlier versions of this
# integration also stored as the config entry model.
LEGACY_MODEL_IDS: dict[str, str] = {
    "WW-Plus": MODEL_ID_PLUS,
    "WW-GW-MF": "ww_gw_mf",
    "WW-GW-ID": "ww_gw_id",
}
