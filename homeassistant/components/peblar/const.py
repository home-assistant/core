"""Constants for the Peblar integration."""

from __future__ import annotations

import logging
from typing import Final

from peblar import ChargeLimiter, CPState

DOMAIN: Final = "peblar"

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
    ChargeLimiter.LOCAL_MODBUS_API: "local_modbus_api",
    ChargeLimiter.LOCAL_REST_API: "local_rest_api",
    ChargeLimiter.LOCAL_SCHEDULED_CHARGING: "local_scheduled_charging",
    ChargeLimiter.OCPP_SMART_CHARGING: "ocpp_smart_charging",
    ChargeLimiter.OVERCURRENT_PROTECTION: "overcurrent_protection",
    ChargeLimiter.PHASE_IMBALANCE: "phase_imbalance",
    ChargeLimiter.POWER_FACTOR: "power_factor",
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
}
