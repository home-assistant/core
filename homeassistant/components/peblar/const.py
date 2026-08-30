"""Constants for the Peblar integration."""

from datetime import timedelta
import logging
from typing import Final

from peblar import ChargeLimiter, CPState

DOMAIN: Final = "peblar"

CONF_EVCC_ID: Final = "evcc_id"
CONF_UID: Final = "uid"

# The stream only makes the poll quicker, so there is no hurry, and no
# point hammering a charger that is switched off.
EVENT_STREAM_RETRY_MINIMUM: Final = timedelta(seconds=5)
EVENT_STREAM_RETRY_MAXIMUM: Final = timedelta(minutes=5)

# How long a charger gets to start rebooting after it was asked to install
# a package. It downloads first, so this is generous: Peblar's own web
# interface waits the same three hours before it gives up.
UPDATE_REBOOT_START_TIMEOUT: Final = timedelta(hours=3)

# And how long it gets to come back once it has actually gone. Peblar
# allows ten minutes for that.
UPDATE_REBOOT_RETURN_TIMEOUT: Final = timedelta(minutes=10)

# How long the charger has to stay away before it counts as having
# rebooted. Peblar allows ten minutes for a reboot, so it is nowhere near
# a matter of seconds; anything shorter is the network dropping a poll.
UPDATE_REBOOT_MINIMUM_DOWNTIME: Final = timedelta(seconds=30)

LOGGER = logging.getLogger(__package__)

PEBLAR_CHARGE_LIMITER_TO_HOME_ASSISTANT = {
    ChargeLimiter.CHARGING_CABLE: "charging_cable",
    ChargeLimiter.CURRENT_LIMITER: "current_limiter",
    ChargeLimiter.DYNAMIC_LOAD_BALANCING: "dynamic_load_balancing",
    ChargeLimiter.EXTERNAL_POWER_LIMIT: "external_power_limit",
    ChargeLimiter.GROUP_LOAD_BALANCING: "group_load_balancing",
    ChargeLimiter.HARDWARE_LIMITATION: "hardware_limitation",
    ChargeLimiter.HIGH_TEMPERATURE: "high_temperature",
    ChargeLimiter.HOUSEHOLD_POWER_LIMIT: "household_power_limit",
    ChargeLimiter.INSTALLATION_LIMIT: "installation_limit",
    ChargeLimiter.INTERNAL_POWER_LIMIT: "internal_power_limit",
    ChargeLimiter.LOCAL_MODBUS_API: "local_modbus_api",
    ChargeLimiter.LOCAL_REST_API: "local_rest_api",
    ChargeLimiter.LOCAL_SCHEDULED_CHARGING: "local_scheduled_charging",
    ChargeLimiter.OCPP_SMART_CHARGING: "ocpp_smart_charging",
    ChargeLimiter.OVERCURRENT_PROTECTION: "overcurrent_protection",
    ChargeLimiter.PHASE_IMBALANCE: "phase_imbalance",
    ChargeLimiter.POWER_FACTOR: "power_factor",
    ChargeLimiter.RESERVED: "reserved",
    ChargeLimiter.SOLAR_CHARGING: "solar_charging",
}

PEBLAR_CP_STATE_TO_HOME_ASSISTANT = {
    CPState.CHARGING_SUSPENDED: "suspended",
    CPState.CHARGING_VENTILATION: "charging",
    CPState.CHARGING: "charging",
    CPState.ERROR: "error",
    CPState.FAULT: "fault",
    CPState.INVALID: "invalid",
    CPState.NO_EV_CONNECTED: "no_ev_connected",
    # The charger cannot measure the CP signal, which is Home Assistant's
    # own unknown state rather than a state of its own.
    CPState.UNKNOWN: None,
}
