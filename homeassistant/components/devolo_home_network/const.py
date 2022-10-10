"""Constants for the devolo Home Network integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "devolo_home_network"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR]

MAC_ADDRESS = "mac_address"
PRODUCT = "product"
SERIAL_NUMBER = "serial_number"
TITLE = "title"

LONG_UPDATE_INTERVAL = timedelta(minutes=5)
SHORT_UPDATE_INTERVAL = timedelta(seconds=15)

CONNECTED_PLC_DEVICES = "connected_plc_devices"
CONNECTED_STATIONS = "connected_stations"
CONNECTED_TO_ROUTER = "connected_to_router"
CONNECTED_WIFI_CLIENTS = "connected_wifi_clients"
NEIGHBORING_WIFI_NETWORKS = "neighboring_wifi_networks"

WIFI_APTYPE = {
    "WIFI_VAP_MAIN_AP": "Main",
    "WIFI_VAP_GUEST_AP": "Guest",
}
WIFI_BANDS = {
    "WIFI_BAND_2G": 2.4,
    "WIFI_BAND_5G": 5,
}
