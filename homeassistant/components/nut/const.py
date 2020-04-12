"""The nut component."""
from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.const import (
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_SECONDS,
    UNIT_PERCENTAGE,
    UNIT_VOLT,
)

DOMAIN = "nut"

PLATFORMS = ["sensor"]

UNDO_UPDATE_LISTENER = "undo_update_listener"

DEFAULT_NAME = "NUT UPS"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3493

KEY_STATUS = "ups.status"
KEY_STATUS_DISPLAY = "ups.status.display"

COORDINATOR = "coordinator"
DEFAULT_SCAN_INTERVAL = 60

PYNUT_DATA = "data"
PYNUT_UNIQUE_ID = "unique_id"
PYNUT_MANUFACTURER = "manufacturer"
PYNUT_MODEL = "model"
PYNUT_FIRMWARE = "firmware"
PYNUT_NAME = "name"

SENSOR_TYPES = {
    "ups.status.display": ["Status", "", "mdi:information-outline", None],
    "ups.status": ["Status Data", "", "mdi:information-outline", None],
    "ups.alarm": ["Alarms", "", "mdi:alarm", None],
    "ups.temperature": [
        "UPS Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "ups.load": ["Load", UNIT_PERCENTAGE, "mdi:gauge", None],
    "ups.load.high": ["Overload Setting", UNIT_PERCENTAGE, "mdi:gauge", None],
    "ups.id": ["System identifier", "", "mdi:information-outline", None],
    "ups.delay.start": ["Load Restart Delay", TIME_SECONDS, "mdi:timer", None],
    "ups.delay.reboot": ["UPS Reboot Delay", TIME_SECONDS, "mdi:timer", None],
    "ups.delay.shutdown": ["UPS Shutdown Delay", TIME_SECONDS, "mdi:timer", None],
    "ups.timer.start": ["Load Start Timer", TIME_SECONDS, "mdi:timer", None],
    "ups.timer.reboot": ["Load Reboot Timer", TIME_SECONDS, "mdi:timer", None],
    "ups.timer.shutdown": ["Load Shutdown Timer", TIME_SECONDS, "mdi:timer", None],
    "ups.test.interval": ["Self-Test Interval", TIME_SECONDS, "mdi:timer", None],
    "ups.test.result": ["Self-Test Result", "", "mdi:information-outline", None],
    "ups.test.date": ["Self-Test Date", "", "mdi:calendar", None],
    "ups.display.language": ["Language", "", "mdi:information-outline", None],
    "ups.contacts": ["External Contacts", "", "mdi:information-outline", None],
    "ups.efficiency": ["Efficiency", UNIT_PERCENTAGE, "mdi:gauge", None],
    "ups.power": ["Current Apparent Power", "VA", "mdi:flash", None],
    "ups.power.nominal": ["Nominal Power", "VA", "mdi:flash", None],
    "ups.realpower": [
        "Current Real Power",
        POWER_WATT,
        "mdi:flash",
        DEVICE_CLASS_POWER,
    ],
    "ups.realpower.nominal": [
        "Nominal Real Power",
        POWER_WATT,
        "mdi:flash",
        DEVICE_CLASS_POWER,
    ],
    "ups.beeper.status": ["Beeper Status", "", "mdi:information-outline", None],
    "ups.type": ["UPS Type", "", "mdi:information-outline", None],
    "ups.watchdog.status": ["Watchdog Status", "", "mdi:information-outline", None],
    "ups.start.auto": ["Start on AC", "", "mdi:information-outline", None],
    "ups.start.battery": ["Start on Battery", "", "mdi:information-outline", None],
    "ups.start.reboot": ["Reboot on Battery", "", "mdi:information-outline", None],
    "ups.shutdown": ["Shutdown Ability", "", "mdi:information-outline", None],
    "battery.charge": [
        "Battery Charge",
        UNIT_PERCENTAGE,
        "mdi:gauge",
        DEVICE_CLASS_BATTERY,
    ],
    "battery.charge.low": ["Low Battery Setpoint", UNIT_PERCENTAGE, "mdi:gauge", None],
    "battery.charge.restart": [
        "Minimum Battery to Start",
        UNIT_PERCENTAGE,
        "mdi:gauge",
        None,
    ],
    "battery.charge.warning": [
        "Warning Battery Setpoint",
        UNIT_PERCENTAGE,
        "mdi:gauge",
        None,
    ],
    "battery.charger.status": ["Charging Status", "", "mdi:information-outline", None],
    "battery.voltage": ["Battery Voltage", UNIT_VOLT, "mdi:flash", None],
    "battery.voltage.nominal": [
        "Nominal Battery Voltage",
        UNIT_VOLT,
        "mdi:flash",
        None,
    ],
    "battery.voltage.low": ["Low Battery Voltage", UNIT_VOLT, "mdi:flash", None],
    "battery.voltage.high": ["High Battery Voltage", UNIT_VOLT, "mdi:flash", None],
    "battery.capacity": ["Battery Capacity", "Ah", "mdi:flash", None],
    "battery.current": ["Battery Current", "A", "mdi:flash", None],
    "battery.current.total": ["Total Battery Current", "A", "mdi:flash", None],
    "battery.temperature": [
        "Battery Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        DEVICE_CLASS_TEMPERATURE,
    ],
    "battery.runtime": ["Battery Runtime", TIME_SECONDS, "mdi:timer", None],
    "battery.runtime.low": ["Low Battery Runtime", TIME_SECONDS, "mdi:timer", None],
    "battery.runtime.restart": [
        "Minimum Battery Runtime to Start",
        TIME_SECONDS,
        "mdi:timer",
        None,
    ],
    "battery.alarm.threshold": [
        "Battery Alarm Threshold",
        "",
        "mdi:information-outline",
        None,
    ],
    "battery.date": ["Battery Date", "", "mdi:calendar", None],
    "battery.mfr.date": ["Battery Manuf. Date", "", "mdi:calendar", None],
    "battery.packs": ["Number of Batteries", "", "mdi:information-outline", None],
    "battery.packs.bad": [
        "Number of Bad Batteries",
        "",
        "mdi:information-outline",
        None,
    ],
    "battery.type": ["Battery Chemistry", "", "mdi:information-outline", None],
    "input.sensitivity": [
        "Input Power Sensitivity",
        "",
        "mdi:information-outline",
        None,
    ],
    "input.transfer.low": ["Low Voltage Transfer", UNIT_VOLT, "mdi:flash", None],
    "input.transfer.high": ["High Voltage Transfer", UNIT_VOLT, "mdi:flash", None],
    "input.transfer.reason": [
        "Voltage Transfer Reason",
        "",
        "mdi:information-outline",
        None,
    ],
    "input.voltage": ["Input Voltage", UNIT_VOLT, "mdi:flash", None],
    "input.voltage.nominal": ["Nominal Input Voltage", UNIT_VOLT, "mdi:flash", None],
    "input.frequency": ["Input Line Frequency", "hz", "mdi:flash", None],
    "input.frequency.nominal": [
        "Nominal Input Line Frequency",
        "hz",
        "mdi:flash",
        None,
    ],
    "input.frequency.status": [
        "Input Frequency Status",
        "",
        "mdi:information-outline",
        None,
    ],
    "output.current": ["Output Current", "A", "mdi:flash", None],
    "output.current.nominal": ["Nominal Output Current", "A", "mdi:flash", None],
    "output.voltage": ["Output Voltage", UNIT_VOLT, "mdi:flash", None],
    "output.voltage.nominal": ["Nominal Output Voltage", UNIT_VOLT, "mdi:flash", None],
    "output.frequency": ["Output Frequency", "hz", "mdi:flash", None],
    "output.frequency.nominal": ["Nominal Output Frequency", "hz", "mdi:flash", None],
}

STATE_TYPES = {
    "OL": "Online",
    "OB": "On Battery",
    "LB": "Low Battery",
    "HB": "High Battery",
    "RB": "Battery Needs Replaced",
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
}

SENSOR_NAME = 0
SENSOR_UNIT = 1
SENSOR_ICON = 2
SENSOR_DEVICE_CLASS = 3
