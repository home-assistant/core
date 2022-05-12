"""Constants for the devolo Home Network integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "devolo_home_network"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

PRODUCT = "product"
SERIAL_NUMBER = "serial_number"
TITLE = "title"

LONG_UPDATE_INTERVAL = timedelta(minutes=5)
SHORT_UPDATE_INTERVAL = timedelta(seconds=15)

CONNECTED_PLC_DEVICES = "connected_plc_devices"
CONNECTED_TO_ROUTER = "connected_to_router"
CONNECTED_WIFI_CLIENTS = "connected_wifi_clients"
NEIGHBORING_WIFI_NETWORKS = "neighboring_wifi_networks"
