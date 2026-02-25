"""Constants for the MyNeomitis integration."""

from enum import Enum

DOMAIN = "myneomitis"
CONF_USER_ID = "user_id"


class Preset(Enum):
    """Preset modes for MyNeomitis devices."""

    COMFORT = ("comfort", 1)
    ECO = ("eco", 2)
    ANTIFROST = ("antifrost", 3)
    STANDBY = ("standby", 4)
    BOOST = ("boost", 6)
    SETPOINT = ("setpoint", 8)
    COMFORT_PLUS = ("comfort_plus", 20)
    AUTO = ("auto", 60)

    def __init__(self, key: str, code: int) -> None:
        """Initialize the preset enum with a key and numeric code."""
        self._key = key
        self._code = code

    @property
    def key(self) -> str:
        """Return the text key for this preset."""
        return self._key

    @property
    def code(self) -> int:
        """Return the numeric code for this preset."""
        return self._code

    def __str__(self) -> str:
        """Return the string representation (the key)."""
        return self._key


PRESET_BY_KEY: dict[str, Preset] = {p.key: p for p in Preset}
PRESET_BY_CODE: dict[int, Preset] = {p.code: p for p in Preset}


PRESET_MODE_MAP: dict[str, int] = {p.key: p.code for p in Preset}
REVERSE_PRESET_MODE_MAP: dict[int, str] = {p.code: p.key for p in Preset}

PRESET_MODE_MODELS: dict[str, list[str]] = {
    "EV30": [
        Preset.SETPOINT.key,
        Preset.BOOST.key,
        Preset.ECO.key,
        Preset.COMFORT.key,
        Preset.AUTO.key,
        Preset.ANTIFROST.key,
        Preset.STANDBY.key,
    ],
    "ECTRL": [
        Preset.SETPOINT.key,
        Preset.BOOST.key,
        Preset.ECO.key,
        Preset.COMFORT.key,
        Preset.COMFORT_PLUS.key,
        Preset.AUTO.key,
        Preset.ANTIFROST.key,
        Preset.STANDBY.key,
    ],
    "ESTAT": [
        Preset.SETPOINT.key,
        Preset.BOOST.key,
        Preset.ECO.key,
        Preset.COMFORT.key,
        Preset.COMFORT_PLUS.key,
        Preset.AUTO.key,
        Preset.ANTIFROST.key,
        Preset.STANDBY.key,
    ],
    "RSS-ECTRL": [
        Preset.SETPOINT.key,
        Preset.BOOST.key,
        Preset.ECO.key,
        Preset.COMFORT.key,
        Preset.COMFORT_PLUS.key,
        Preset.AUTO.key,
        Preset.ANTIFROST.key,
        Preset.STANDBY.key,
    ],
    "NTD": [
        Preset.SETPOINT.key,
        Preset.ECO.key,
        Preset.COMFORT.key,
        Preset.AUTO.key,
        Preset.ANTIFROST.key,
        Preset.STANDBY.key,
    ],
    "ETRV": [
        Preset.SETPOINT.key,
        Preset.ECO.key,
        Preset.COMFORT.key,
        Preset.ANTIFROST.key,
        Preset.STANDBY.key,
    ],
}

PRESET_MODE_MAP_RELAIS: dict[str, int] = {
    "on": 1,
    "off": 2,
    "auto": PRESET_BY_KEY["auto"].code,
}
REVERSE_PRESET_MODE_MAP_RELAIS: dict[int, str] = {
    v: k for k, v in PRESET_MODE_MAP_RELAIS.items()
}

PRESET_MODE_MAP_UFH: dict[str, int] = {"heating": 0, "cooling": 1}
REVERSE_PRESET_MODE_MAP_UFH: dict[int, str] = {
    v: k for k, v in PRESET_MODE_MAP_UFH.items()
}

PRESET_MODE_SELECT_EXTRAS: dict[str, int] = {"eco_1": 40, "eco_2": 41}
