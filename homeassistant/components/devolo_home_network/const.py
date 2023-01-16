"""Constants for the devolo Home Network integration."""

from datetime import timedelta

from devolo_plc_api.device_api import (
    WIFI_BAND_2G,
    WIFI_BAND_5G,
    WIFI_VAP_GUEST_AP,
    WIFI_VAP_MAIN_AP,
)

from homeassistant.const import Platform

DOMAIN = "devolo_home_network"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
]

PRODUCT = "product"
SERIAL_NUMBER = "serial_number"
TITLE = "title"

LONG_UPDATE_INTERVAL = timedelta(minutes=5)
SHORT_UPDATE_INTERVAL = timedelta(seconds=15)

CONNECTED_PLC_DEVICES = "connected_plc_devices"
CONNECTED_TO_ROUTER = "connected_to_router"
CONNECTED_WIFI_CLIENTS = "connected_wifi_clients"
NEIGHBORING_WIFI_NETWORKS = "neighboring_wifi_networks"
SWITCH_GUEST_WIFI = "switch_guest_wifi"
SWITCH_LEDS = "switch_leds"

WIFI_APTYPE = {
    WIFI_VAP_MAIN_AP: "Main",
    WIFI_VAP_GUEST_AP: "Guest",
}
WIFI_BANDS = {
    WIFI_BAND_2G: 2.4,
    WIFI_BAND_5G: 5,
}
