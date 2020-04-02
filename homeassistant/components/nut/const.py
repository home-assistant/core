"""The nut component."""
from homeassistant.const import POWER_WATT, TEMP_CELSIUS, TIME_SECONDS, UNIT_PERCENTAGE

DOMAIN = "nut"

PLATFORMS = ["sensor"]


DEFAULT_NAME = "NUT UPS"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3493

KEY_STATUS = "ups.status"
KEY_STATUS_DISPLAY = "ups.status.display"

PYNUT_DATA = "data"
PYNUT_STATUS = "status"
PYNUT_UNIQUE_ID = "unique_id"
PYNUT_MANUFACTURER = "manufacturer"
PYNUT_MODEL = "model"
PYNUT_FIRMWARE = "firmware"

SENSOR_TYPES = {
    "ups.status.display": ["Status", "", "mdi:information-outline"],
    "ups.status": ["Status Data", "", "mdi:information-outline"],
    "ups.alarm": ["Alarms", "", "mdi:alarm"],
    "ups.temperature": ["UPS Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "ups.load": ["Load", UNIT_PERCENTAGE, "mdi:gauge"],
    "ups.load.high": ["Overload Setting", UNIT_PERCENTAGE, "mdi:gauge"],
    "ups.id": ["System identifier", "", "mdi:information-outline"],
    "ups.delay.start": ["Load Restart Delay", TIME_SECONDS, "mdi:timer"],
    "ups.delay.reboot": ["UPS Reboot Delay", TIME_SECONDS, "mdi:timer"],
    "ups.delay.shutdown": ["UPS Shutdown Delay", TIME_SECONDS, "mdi:timer"],
    "ups.timer.start": ["Load Start Timer", TIME_SECONDS, "mdi:timer"],
    "ups.timer.reboot": ["Load Reboot Timer", TIME_SECONDS, "mdi:timer"],
    "ups.timer.shutdown": ["Load Shutdown Timer", TIME_SECONDS, "mdi:timer"],
    "ups.test.interval": ["Self-Test Interval", TIME_SECONDS, "mdi:timer"],
    "ups.test.result": ["Self-Test Result", "", "mdi:information-outline"],
    "ups.test.date": ["Self-Test Date", "", "mdi:calendar"],
    "ups.display.language": ["Language", "", "mdi:information-outline"],
    "ups.contacts": ["External Contacts", "", "mdi:information-outline"],
    "ups.efficiency": ["Efficiency", UNIT_PERCENTAGE, "mdi:gauge"],
    "ups.power": ["Current Apparent Power", "VA", "mdi:flash"],
    "ups.power.nominal": ["Nominal Power", "VA", "mdi:flash"],
    "ups.realpower": ["Current Real Power", POWER_WATT, "mdi:flash"],
    "ups.realpower.nominal": ["Nominal Real Power", POWER_WATT, "mdi:flash"],
    "ups.beeper.status": ["Beeper Status", "", "mdi:information-outline"],
    "ups.type": ["UPS Type", "", "mdi:information-outline"],
    "ups.watchdog.status": ["Watchdog Status", "", "mdi:information-outline"],
    "ups.start.auto": ["Start on AC", "", "mdi:information-outline"],
    "ups.start.battery": ["Start on Battery", "", "mdi:information-outline"],
    "ups.start.reboot": ["Reboot on Battery", "", "mdi:information-outline"],
    "ups.shutdown": ["Shutdown Ability", "", "mdi:information-outline"],
    "battery.charge": ["Battery Charge", UNIT_PERCENTAGE, "mdi:gauge"],
    "battery.charge.low": ["Low Battery Setpoint", UNIT_PERCENTAGE, "mdi:gauge"],
    "battery.charge.restart": [
        "Minimum Battery to Start",
        UNIT_PERCENTAGE,
        "mdi:gauge",
    ],
    "battery.charge.warning": [
        "Warning Battery Setpoint",
        UNIT_PERCENTAGE,
        "mdi:gauge",
    ],
    "battery.charger.status": ["Charging Status", "", "mdi:information-outline"],
    "battery.voltage": ["Battery Voltage", "V", "mdi:flash"],
    "battery.voltage.nominal": ["Nominal Battery Voltage", "V", "mdi:flash"],
    "battery.voltage.low": ["Low Battery Voltage", "V", "mdi:flash"],
    "battery.voltage.high": ["High Battery Voltage", "V", "mdi:flash"],
    "battery.capacity": ["Battery Capacity", "Ah", "mdi:flash"],
    "battery.current": ["Battery Current", "A", "mdi:flash"],
    "battery.current.total": ["Total Battery Current", "A", "mdi:flash"],
    "battery.temperature": ["Battery Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "battery.runtime": ["Battery Runtime", TIME_SECONDS, "mdi:timer"],
    "battery.runtime.low": ["Low Battery Runtime", TIME_SECONDS, "mdi:timer"],
    "battery.runtime.restart": [
        "Minimum Battery Runtime to Start",
        TIME_SECONDS,
        "mdi:timer",
    ],
    "battery.alarm.threshold": [
        "Battery Alarm Threshold",
        "",
        "mdi:information-outline",
    ],
    "battery.date": ["Battery Date", "", "mdi:calendar"],
    "battery.mfr.date": ["Battery Manuf. Date", "", "mdi:calendar"],
    "battery.packs": ["Number of Batteries", "", "mdi:information-outline"],
    "battery.packs.bad": ["Number of Bad Batteries", "", "mdi:information-outline"],
    "battery.type": ["Battery Chemistry", "", "mdi:information-outline"],
    "input.sensitivity": ["Input Power Sensitivity", "", "mdi:information-outline"],
    "input.transfer.low": ["Low Voltage Transfer", "V", "mdi:flash"],
    "input.transfer.high": ["High Voltage Transfer", "V", "mdi:flash"],
    "input.transfer.reason": ["Voltage Transfer Reason", "", "mdi:information-outline"],
    "input.voltage": ["Input Voltage", "V", "mdi:flash"],
    "input.voltage.nominal": ["Nominal Input Voltage", "V", "mdi:flash"],
    "input.frequency": ["Input Line Frequency", "hz", "mdi:flash"],
    "input.frequency.nominal": ["Nominal Input Line Frequency", "hz", "mdi:flash"],
    "input.frequency.status": ["Input Frequency Status", "", "mdi:information-outline"],
    "output.current": ["Output Current", "A", "mdi:flash"],
    "output.current.nominal": ["Nominal Output Current", "A", "mdi:flash"],
    "output.voltage": ["Output Voltage", "V", "mdi:flash"],
    "output.voltage.nominal": ["Nominal Output Voltage", "V", "mdi:flash"],
    "output.frequency": ["Output Frequency", "hz", "mdi:flash"],
    "output.frequency.nominal": ["Nominal Output Frequency", "hz", "mdi:flash"],
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
