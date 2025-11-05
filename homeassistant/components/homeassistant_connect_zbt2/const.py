"""Constants for the Home Assistant Connect ZBT-2 integration."""

from homeassistant.generated.countries import COUNTRIES

DOMAIN = "homeassistant_connect_zbt2"

NABU_CASA_FIRMWARE_RELEASES_URL = (
    "https://api.github.com/repos/NabuCasa/silabs-firmware-builder/releases"
)

FIRMWARE = "firmware"
FIRMWARE_VERSION = "firmware_version"
SERIAL_NUMBER = "serial_number"
MANUFACTURER = "manufacturer"
PRODUCT = "product"
DESCRIPTION = "description"
PID = "pid"
VID = "vid"
DEVICE = "device"

HARDWARE_NAME = "Home Assistant Connect ZBT-2"

RADIO_TX_POWER_DBM_DEFAULT = 8
RADIO_TX_POWER_DBM_BY_COUNTRY = {
    # EU Member States
    "AT": 10,
    "BE": 10,
    "BG": 10,
    "HR": 10,
    "CY": 10,
    "CZ": 10,
    "DK": 10,
    "EE": 10,
    "FI": 10,
    "FR": 10,
    "DE": 10,
    "GR": 10,
    "HU": 10,
    "IE": 10,
    "IT": 10,
    "LV": 10,
    "LT": 10,
    "LU": 10,
    "MT": 10,
    "NL": 10,
    "PL": 10,
    "PT": 10,
    "RO": 10,
    "SK": 10,
    "SI": 10,
    "ES": 10,
    "SE": 10,
    # EEA Members
    "IS": 10,
    "LI": 10,
    "NO": 10,
    # Standards harmonized with RED or ETSI
    "CH": 10,
    "GB": 10,
    "TR": 10,
    "AL": 10,
    "BA": 10,
    "GE": 10,
    "MD": 10,
    "ME": 10,
    "MK": 10,
    "RS": 10,
    "UA": 10,
    # Other CEPT nations
    "AD": 10,
    "AZ": 10,
    "MC": 10,
    "SM": 10,
    "VA": 10,
}

assert set(RADIO_TX_POWER_DBM_BY_COUNTRY) <= COUNTRIES
