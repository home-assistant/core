"""The nut component."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "nut"

PLATFORMS = [
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

DEFAULT_NAME = "NUT UPS"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3493

KEY_STATUS = "ups.status"
KEY_STATUS_DISPLAY = "ups.status.display"

STATE_TYPES = {
    "OL": "Online",
    "OB": "On Battery",
    "LB": "Low Battery",
    "HB": "High Battery",
    "RB": "Battery Needs Replacement",
    "CHRG": "Battery Charging",
    "DISCHRG": "Battery Discharging",
    "BYPASS": "Bypass Active",
    "CAL": "Runtime Calibration",
    "OFF": "Offline",
    "OVER": "Overloaded",
    "TRIM": "Trimming Voltage",
    "BOOST": "Boosting Voltage",
    "FSD": "Forced Shutdown",
    "ALARM": "Alarm",
    "HE": "ECO Mode",
    "TEST": "Battery Testing",
}

COMMAND_BEEPER_DISABLE = "beeper.disable"
COMMAND_BEEPER_ENABLE = "beeper.enable"
COMMAND_BEEPER_MUTE = "beeper.mute"
COMMAND_BEEPER_TOGGLE = "beeper.toggle"
COMMAND_BYPASS_START = "bypass.start"
COMMAND_BYPASS_STOP = "bypass.stop"
COMMAND_CALIBRATE_START = "calibrate.start"
COMMAND_CALIBRATE_STOP = "calibrate.stop"
COMMAND_LOAD_OFF = "load.off"
COMMAND_LOAD_ON = "load.on"
COMMAND_RESET_INPUT_MINMAX = "reset.input.minmax"
COMMAND_RESET_WATCHDOG = "reset.watchdog"
COMMAND_SHUTDOWN_REBOOT = "shutdown.reboot"
COMMAND_SHUTDOWN_REBOOT_GRACEFUL = "shutdown.reboot.graceful"
COMMAND_SHUTDOWN_RETURN = "shutdown.return"
COMMAND_SHUTDOWN_STAYOFF = "shutdown.stayoff"
COMMAND_SHUTDOWN_STOP = "shutdown.stop"
COMMAND_TEST_BATTERY_START = "test.battery.start"
COMMAND_TEST_BATTERY_START_DEEP = "test.battery.start.deep"
COMMAND_TEST_BATTERY_START_QUICK = "test.battery.start.quick"
COMMAND_TEST_BATTERY_STOP = "test.battery.stop"
COMMAND_TEST_FAILURE_START = "test.failure.start"
COMMAND_TEST_FAILURE_STOP = "test.failure.stop"
COMMAND_TEST_PANEL_START = "test.panel.start"
COMMAND_TEST_PANEL_STOP = "test.panel.stop"
COMMAND_TEST_SYSTEM_START = "test.system.start"

INTEGRATION_SUPPORTED_COMMANDS = {
    COMMAND_BEEPER_DISABLE,
    COMMAND_BEEPER_ENABLE,
    COMMAND_BEEPER_MUTE,
    COMMAND_BEEPER_TOGGLE,
    COMMAND_BYPASS_START,
    COMMAND_BYPASS_STOP,
    COMMAND_CALIBRATE_START,
    COMMAND_CALIBRATE_STOP,
    COMMAND_LOAD_OFF,
    COMMAND_LOAD_ON,
    COMMAND_RESET_INPUT_MINMAX,
    COMMAND_RESET_WATCHDOG,
    COMMAND_SHUTDOWN_REBOOT,
    COMMAND_SHUTDOWN_REBOOT_GRACEFUL,
    COMMAND_SHUTDOWN_RETURN,
    COMMAND_SHUTDOWN_STAYOFF,
    COMMAND_SHUTDOWN_STOP,
    COMMAND_TEST_BATTERY_START,
    COMMAND_TEST_BATTERY_START_DEEP,
    COMMAND_TEST_BATTERY_START_QUICK,
    COMMAND_TEST_BATTERY_STOP,
    COMMAND_TEST_FAILURE_START,
    COMMAND_TEST_FAILURE_STOP,
    COMMAND_TEST_PANEL_START,
    COMMAND_TEST_PANEL_STOP,
    COMMAND_TEST_SYSTEM_START,
}
