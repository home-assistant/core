"""Const for LIFX."""

DOMAIN = "lifx"

TARGET_ANY = "00:00:00:00:00:00"

DISCOVERY_INTERVAL = 10
MESSAGE_TIMEOUT = 1.65
MESSAGE_RETRIES = 5
OVERALL_TIMEOUT = 9
UNAVAILABLE_GRACE = 90

CONF_SERIAL = "serial"

IDENTIFY_WAVEFORM = {
    "transient": True,
    "color": [0, 0, 1, 3500],
    "skew_ratio": 0,
    "period": 1000,
    "cycles": 3,
    "waveform": 1,
    "set_hue": True,
    "set_saturation": True,
    "set_brightness": True,
    "set_kelvin": True,
}
IDENTIFY = "identify"
RESTART = "restart"

HEV_CYCLE_DURATION = "hev_cycle_duration"
HEV_CYCLE_REMAINING = "hev_cycle_remaining"
HEV_CYCLE_LAST_POWER = "hev_cycle_last_power"
HEV_CYCLE_LAST_RESULT = "last_hev_cycle_result"

DATA_LIFX_MANAGER = "lifx_manager"

ATTR_RSSI = "rssi"
