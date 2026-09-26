"""Shared constants for the Spin EV Charger tests."""

from spinev_ble import ChargerState, ChargerStatus

from homeassistant.components.spinev.const import (
    CONF_CONNECTION_MODE,
    CONF_SERIAL,
    DEFAULT_CONNECTION_MODE,
)
from homeassistant.const import CONF_ADDRESS

ADDRESS = "AA:BB:CC:DD:EE:FF"
SERIAL = "123456789012"
#: The charger advertises its serial with a leading space and an address suffix.
ADVERTISED_NAME = f" {SERIAL}_EEFF"
SERVICE_UUID = "49535343-fe7d-4ae5-8fa9-9fafd205e455"

ENTRY_DATA = {CONF_ADDRESS: ADDRESS, CONF_SERIAL: SERIAL}
ENTRY_OPTIONS = {CONF_CONNECTION_MODE: DEFAULT_CONNECTION_MODE}

STATE_SENSOR = "sensor.123456789012_state"

STATUS = ChargerStatus(
    state=ChargerState.CHARGING,
    state_value=4,
    power_w=7360.0,
    voltage_v=230.0,
    current_a=32.0,
    current_limit_a=32.0,
    session_energy_kwh=12.5,
    session_seconds=3600,
    lifetime_energy_kwh=1234.5,
    lifetime_seconds=360000,
    firmware_version="35.24.4.32",
    alarms=(),
)

IDLE_STATUS = ChargerStatus(
    state=ChargerState.IDLE,
    state_value=2,
    power_w=0.0,
    voltage_v=230.0,
    current_a=0.0,
    current_limit_a=32.0,
    session_energy_kwh=0.0,
    session_seconds=0,
    lifetime_energy_kwh=1234.5,
    lifetime_seconds=360000,
    firmware_version="35.24.4.32",
    alarms=(),
)
