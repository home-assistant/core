"""Constants for Airthings BLE."""

from airthings_ble import AirthingsDeviceType

DOMAIN = "airthings_ble"
MFCT_ID = 820

VOLUME_BECQUEREL = "Bq/m³"
VOLUME_PICOCURIE = "pCi/L"

DEVICE_MODEL = "device_model"

DEFAULT_SCAN_INTERVAL = 300
DEVICE_SPECIFIC_SCAN_INTERVAL = {AirthingsDeviceType.CORENTIUM_HOME_2.value: 1800}

MAX_RETRIES_AFTER_STARTUP = 5
