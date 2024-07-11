"""Constants of the Xiaomi Aqara component."""

DOMAIN = "xiaomi_aqara"

GATEWAYS_KEY = "gateways"
LISTENER_KEY = "listener"
KEY_UNSUB_STOP = "unsub_stop"
KEY_SETUP_LOCK = "setup_lock"

ZEROCONF_GATEWAY = "lumi-gateway"
ZEROCONF_ACPARTNER = "lumi-acpartner"

CONF_INTERFACE = "interface"
CONF_KEY = "key"
CONF_SID = "sid"

DEFAULT_DISCOVERY_RETRY = 5

BATTERY_MODELS = [
    "sensor_ht",
    "weather",
    "weather.v1",
    "sensor_motion.aq2",
    "vibration",
    "magnet",
    "sensor_magnet",
    "sensor_magnet.aq2",
    "motion",
    "sensor_motion",
    "sensor_motion.aq2",
    "switch",
    "sensor_switch",
    "sensor_switch.aq2",
    "sensor_switch.aq3",
    "remote.b1acn01",
    "86sw1",
    "sensor_86sw1",
    "sensor_86sw1.aq1",
    "remote.b186acn01",
    "remote.b186acn02",
    "86sw2",
    "sensor_86sw2",
    "sensor_86sw2.aq1",
    "remote.b286acn01",
    "remote.b286acn02",
    "cube",
    "sensor_cube",
    "sensor_cube.aqgl01",
    "smoke",
    "sensor_smoke",
    "sensor_wleak.aq1",
    "vibration",
    "vibration.aq1",
    "curtain",
    "curtain.aq2",
    "curtain.hagl04",
    "lock.aq1",
    "lock.acn02",
]

POWER_MODELS = [
    "86plug",
    "ctrl_86plug",
    "ctrl_86plug.aq1",
]
