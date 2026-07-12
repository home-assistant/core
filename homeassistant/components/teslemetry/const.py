"""Constants used by Teslemetry integration."""

from enum import StrEnum
import logging

DOMAIN = "teslemetry"

LOGGER = logging.getLogger(__package__)

# OAuth
AUTHORIZE_URL = "https://teslemetry.com/connect"
TOKEN_URL = "https://api.teslemetry.com/oauth/token"
CLIENT_ID = "homeassistant"

# Config subentry type holding a vehicle's pairing config
SUBENTRY_TYPE_VEHICLE = "vehicle"

# Vehicle subentry data key. A vehicle subentry also stores CONF_ADDRESS (from
# homeassistant.const) once paired; its presence enables Bluetooth-first routing.
CONF_VIN = "vin"

# File holding the integration's EC private key used to sign BLE commands. The
# matching public/virtual key is what the user adds to the vehicle when pairing.
VEHICLE_KEY_FILE = "tesla_vehicle.key"

# hass.data key for the shared TeslaBluetooth parent (holds the private key).
BLE_PARENT_KEY = f"{DOMAIN}_ble_parent"

# hass.data key for the lock serializing first-time BLE parent/key-file init.
BLE_PARENT_LOCK_KEY = f"{DOMAIN}_ble_parent_lock"

ENERGY_HISTORY_FIELDS = [
    "solar_energy_exported",
    "generator_energy_exported",
    "grid_energy_imported",
    "grid_services_energy_imported",
    "grid_services_energy_exported",
    "grid_energy_exported_from_solar",
    "grid_energy_exported_from_generator",
    "grid_energy_exported_from_battery",
    "battery_energy_exported",
    "battery_energy_imported_from_grid",
    "battery_energy_imported_from_solar",
    "battery_energy_imported_from_generator",
    "consumer_energy_imported_from_grid",
    "consumer_energy_imported_from_solar",
    "consumer_energy_imported_from_battery",
    "consumer_energy_imported_from_generator",
    "total_home_usage",
    "total_battery_charge",
    "total_battery_discharge",
    "total_solar_generation",
    "total_grid_energy_exported",
]


# Vehicle metadata "issue" values that map to an actionable repair issue, with
# an optional "learn more" URL the user can visit to resolve it. The "no_data"
# issue is intentionally ignored as it is not user-actionable.
VEHICLE_ISSUE_LEARN_MORE: dict[str, str | None] = {
    "key": "https://teslemetry.com/key",
    "streaming_toggle": None,
}


class TeslemetryState(StrEnum):
    """Teslemetry Vehicle States."""

    ONLINE = "online"
    ASLEEP = "asleep"
    OFFLINE = "offline"


class TeslemetryClimateSide(StrEnum):
    """Teslemetry Climate Keeper Modes."""

    DRIVER = "driver_temp"
    PASSENGER = "passenger_temp"
