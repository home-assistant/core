"""The nut component."""

from __future__ import annotations

from homeassistant.const import Platform

from .nut_command import NutCommand

DOMAIN = "nut"

PLATFORMS = [Platform.SENSOR]

DEFAULT_NAME = "NUT UPS"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3493

KEY_STATUS = "ups.status"
KEY_STATUS_DISPLAY = "ups.status.display"

DEFAULT_SCAN_INTERVAL = 60

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


COMMAND_BEEPER_DISABLE = NutCommand("beeper.disable")
COMMAND_BEEPER_ENABLE = NutCommand("beeper.enable")
COMMAND_BEEPER_MUTE = NutCommand("beeper.mute")
COMMAND_BEEPER_TOGGLE = NutCommand("beeper.toggle")
COMMAND_BYPASS_START = NutCommand("bypass.start")
COMMAND_BYPASS_STOP = NutCommand("bypass.stop")
COMMAND_CALIBRATE_START = NutCommand("calibrate.start")
COMMAND_CALIBRATE_STOP = NutCommand("calibrate.stop")
COMMAND_LOAD_OFF = NutCommand("load.off")
COMMAND_LOAD_ON = NutCommand("load.on")
COMMAND_RESET_INPUT_MINMAX = NutCommand("reset.input.minmax")
COMMAND_RESET_WATCHDOG = NutCommand("reset.watchdog")
COMMAND_SHUTDOWN_REBOOT = NutCommand("shutdown.reboot")
COMMAND_SHUTDOWN_REBOOT_GRACEFUL = NutCommand("shutdown.reboot.graceful")
COMMAND_SHUTDOWN_RETURN = NutCommand("shutdown.return")
COMMAND_SHUTDOWN_STAYOFF = NutCommand("shutdown.stayoff")
COMMAND_SHUTDOWN_STOP = NutCommand("shutdown.stop")
COMMAND_TEST_BATTERY_START = NutCommand("test.battery.start")
COMMAND_TEST_BATTERY_START_DEEP = NutCommand("test.battery.start.deep")
COMMAND_TEST_BATTERY_START_QUICK = NutCommand("test.battery.start.quick")
COMMAND_TEST_BATTERY_STOP = NutCommand("test.battery.stop")
COMMAND_TEST_FAILURE_START = NutCommand("test.failure.start")
COMMAND_TEST_FAILURE_STOP = NutCommand("test.failure.stop")
COMMAND_TEST_PANEL_START = NutCommand("test.panel.start")
COMMAND_TEST_PANEL_STOP = NutCommand("test.panel.stop")
COMMAND_TEST_SYSTEM_START = NutCommand("test.system.start")

INTEGRATION_SUPPORTED_COMMANDS = [
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
]

INTEGRATION_SUPPORTED_COMMANDS_DICT = {
    cmd.command_string: cmd for cmd in INTEGRATION_SUPPORTED_COMMANDS
}
