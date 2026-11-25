"""Constants for the APsystems Lake_6 local API client.

Single source of truth for the Lake_6 integration: endpoints and timeouts,
business status codes, enumeration strings, numeric ranges, and the mapping
between raw JSON field names and entity keys.

Every name is prefixed with LAKE6_ so it cannot clash with the EZ1 constants
that live in the parent package. This module holds constants only.
"""

from typing import Final

# Lake_6 serves plain HTTP on port 80, unlike the EZ1 8050.
LAKE6_DEFAULT_PORT: Final = 80

# Timeout for a single HTTP request. One refresh issues several requests in
# sequence, so the worst case is roughly "timeout x request count". Ten seconds
# keeps an offline device from stalling a refresh without delaying the
# unavailable state for too long.
LAKE6_REQUEST_TIMEOUT: Final = 10

LAKE6_ENDPOINT_DEVICES: Final = "/devices"
LAKE6_ENDPOINT_ENERGIES: Final = "/energies"
LAKE6_ENDPOINT_ALARMS: Final = "/alarms"
LAKE6_ENDPOINT_MODES: Final = "/modes"
LAKE6_ENDPOINT_CONTROL_PANELS: Final = "/control-panels"

# A battery moves over minutes rather than seconds, so 60 seconds replaces the
# 12 second EZ1 cadence and cuts recorder writes to a fifth.
LAKE6_UPDATE_INTERVAL: Final = 60

# /modes almost never changes, so it is throttled by timestamp inside the
# update. A dirty flag forces a fetch after a write so the UI does not lag.
LAKE6_MODES_UPDATE_INTERVAL: Final = 300

# /control-panels only carries a value while a manual run is active, so it
# shares the /modes cadence for a negligible extra cost.
LAKE6_CONTROL_PANEL_UPDATE_INTERVAL: Final = 300

# The body code is unrelated to the HTTP status: only code == 200 is success.
# Anything else is a failure, and the raw code is logged as-is.
LAKE6_CODE_SUCCESS: Final = 200

# /control-panels envelopes omit code in practice (missing on GET, present on
# POST), so a missing code falls back to the message. Every other endpoint
# treats a missing code as a failure.
LAKE6_MESSAGE_SUCCESS: Final = "SUCCESS"

# Log only. Entity states and user facing text come from strings.json.
# V1.5.2 dropped 1004 from the published table; it is kept so firmware built
# against an older document still logs something readable.
LAKE6_CODE_DESCRIPTIONS: Final[dict[int, str]] = {
    1001: "data length error",
    1002: "data format error",
    1003: "internal error",
    1004: "internal error",
    2001: "internal communication error",
}

# Device code -> entity state. Exposing the raw "1"/"2" would leak firmware
# enumerations into the entity layer and make a code change touch every entity.
LAKE6_BATTERY_STATUS_TO_STATE: Final[dict[str, str]] = {
    "1": "idle",
    "2": "charging",
    "3": "discharging",
    "4": "fault",
    "5": "shutdown",
    "6": "no_communication",
    "7": "heating",
}

LAKE6_OPERATING_MODE_TO_STATE: Final[dict[str, str]] = {
    "1": "ai",
    "2": "self_consumption",
    "3": "time_of_use",
    "4": "backup",
}

# Reverse lookup used when writing a mode back to the device.
LAKE6_OPERATING_MODE_FROM_STATE: Final[dict[str, str]] = {
    state: code for code, state in LAKE6_OPERATING_MODE_TO_STATE.items()
}

# AI mode cannot be selected from the integration; it is app-only.
LAKE6_MODE_STATE_AI: Final = "ai"

# time_cfg is only honoured in time-of-use mode, which also gates the entity.
LAKE6_MODE_STATE_TIME_OF_USE: Final = "time_of_use"

# time_cfg[].TM[].F -> state string. An unknown function code yields None
# instead of breaking the whole table.
LAKE6_TOU_FUNCTION_TO_STATE: Final[dict[str, str]] = {
    "1": "charge",
    "2": "discharge",
    "3": "self_consumption",
}

# Reverse lookup for writing back; keep in sync with the table above.
LAKE6_TOU_FUNCTION_FROM_STATE: Final[dict[str, str]] = {
    state: code for code, state in LAKE6_TOU_FUNCTION_TO_STATE.items()
}

# F="3" means self-consumption, where the power field does not apply.
LAKE6_TOU_STATE_SELF_CONSUMPTION: Final = "self_consumption"

# A plan holds 1 to 24 rules: weekdays is any subset of 1-7 and each rule is
# exactly one time block. The whole plan lives in a single text entity rather
# than one entity per rule, and how many rules fit is bounded by the state
# length, see LAKE6_TOU_TEXT_MAX_RULES.
LAKE6_TOU_MAX_RULES: Final = 24

# TM[].FI.P: 0 to 2500 W for charge and discharge; unused when F=3.
# The FI.P description in V1.5.2 still mentions power_limit, but that field was
# removed in V1.5.1, so the clause no longer limits anything.
LAKE6_TOU_POWER_MIN: Final = 0
LAKE6_TOU_POWER_MAX: Final = 2500

# FI.GC / FI.GD: F="1" carries the grid charge permit, F="2" the battery-to-grid
# discharge permit. The firmware forces both to 1 and ignores any written value,
# so they are set for shape only. The key that does not match the current
# function is dropped instead of being carried over from the previous one.
LAKE6_TOU_PERMIT_KEYS: Final = ("GC", "GD")
LAKE6_TOU_TEXT_FUNCTION_TO_PERMIT: Final[dict[str, str]] = {
    "charge": "GC",
    "discharge": "GD",
}

# The whole time_cfg is packed into one text entity on a single line:
#
#   09:00-09:10|discharge|200|1234567|1;10:00-10:10|self|-|1234567|1
#
# Field order is always time | function | power | weekdays | enabled. A text
# entity is a single-line input where newlines cannot be typed, so rules are
# separated by ";" instead.
LAKE6_TOU_TEXT_MAX_LENGTH: Final = 255
LAKE6_TOU_TEXT_FIELD_SEPARATOR: Final = "|"
LAKE6_TOU_TEXT_RULE_SEPARATOR: Final = ";"

# The longest rule "00:00-23:59|discharge|2500|1234567|1" is 36 characters.
# Counting the separator as 37, (255 + 1) // 37 = 6 rules fit.
LAKE6_TOU_TEXT_ROW_MAX_LENGTH: Final = 36
LAKE6_TOU_TEXT_MAX_RULES: Final = (LAKE6_TOU_TEXT_MAX_LENGTH + 1) // (
    LAKE6_TOU_TEXT_ROW_MAX_LENGTH + 1
)

# Abbreviation for self-consumption inside the text. The 255 character budget
# is tight, and every saved character buys room for another rule.
LAKE6_TOU_TEXT_FUNCTION_SELF: Final = "self"

# Abbreviation -> device code for the text format.
LAKE6_TOU_TEXT_FUNCTION_TO_CODE: Final[dict[str, str]] = {
    "charge": "1",
    "discharge": "2",
    "self": "3",
}

# Decoded state -> abbreviation. A missing key means the firmware reported an
# unknown function code.
LAKE6_TOU_STATE_TO_TEXT_FUNCTION: Final[dict[str, str]] = {
    "charge": "charge",
    "discharge": "discharge",
    "self_consumption": "self",
}

# Self-consumption has no power, so "-" keeps the field count fixed.
LAKE6_TOU_TEXT_POWER_PLACEHOLDER: Final = "-"

# Weekdays use a compact form: "12345" equals [1,2,3,4,5]. Parsing also accepts
# "1-5" and "1,3,5", but the state is always rendered compactly.
LAKE6_TOU_TEXT_WEEKDAY_RANGE_SEPARATOR: Final = "-"
LAKE6_TOU_TEXT_WEEKDAY_LIST_SEPARATOR: Final = ","

# /devices on Lake does not report maxPower/minPower, unlike EZ1, so the ranges
# have to live here instead of the entity implementations.
#
# dod is what the product calls backupSoc: the lowest state of charge the
# battery may discharge to in backup mode. dod=15 discharges the most and
# dod=90 almost not at all, so a larger number is more conservative. That is the
# opposite direction of the usual depth of discharge definition, which is why
# the entity is named "Backup SOC" rather than "Depth of Discharge".
#
# Ranges follow Local API V1.5.2. A value inside the range cannot tell a wider
# limit apart, so the document is the only source.
#
# power_limit was removed in V1.5.1 and backup_charP in V1.5.2. Older firmware
# still returns both, so they are ignored: not parsed, not exposed, never
# written back.
LAKE6_DEPTH_OF_DISCHARGE_MIN: Final = 15
LAKE6_DEPTH_OF_DISCHARGE_MAX: Final = 90
LAKE6_DEPTH_OF_DISCHARGE_STEP: Final = 1

# Raw JSON field -> Lake6Energies attribute, which doubles as the entity key.
LAKE6_ENERGY_FIELD_TO_ATTR: Final[dict[str, str]] = {
    "bat_soc": "battery_soc",
    "bat_temp": "battery_temperature",
    "dev_temp": "device_temperature",
    "bat_impE": "battery_charge_energy",
    "bat_expE": "battery_discharge_energy",
    "ongrid_expE": "grid_export_energy",
    "ongrid_impE": "grid_import_energy",
    "offgrid_expE": "offgrid_export_energy",
    "offgrid_impE": "offgrid_import_energy",
    "bat_power": "battery_power",
    "ongrid_power": "grid_power",
    "offgrid_power": "offgrid_power",
}

# Raw JSON field -> Lake6Alarms attribute. Note dev_temp: it is a temperature
# reading in /energies but a temperature protection alarm bit in /alarms, so it
# must be renamed to device_temperature_protection and never share the entry
# above.
LAKE6_ALARM_FIELD_TO_ATTR: Final[dict[str, str]] = {
    "bat_overtemp": "battery_over_temperature",
    "bat_undertemp": "battery_under_temperature",
    "bat_comm_err": "battery_communication_error",
    "bat_overvolt": "battery_over_voltage",
    "bat_undervolt": "battery_under_voltage",
    "bat_overcur": "battery_over_current",
    "bat_ie": "battery_internal_error",
    "dev_temp": "device_temperature_protection",
    "dev_sys_err": "device_system_error",
    "bat_shutdown": "battery_shutdown",
    "grid_anomaly": "grid_anomaly",
    "offgrid_overcur": "offgrid_over_current",
    "offgrid_shortcir": "offgrid_short_circuit",
    "bat_cal": "battery_calibration",
}

# Raw JSON field -> Lake6Modes attribute. The dod attribute carries backupSoc
# semantics, see the numeric range block above.
LAKE6_MODE_FIELD_TO_ATTR: Final[dict[str, str]] = {
    "mode": "operating_mode",
    "eco": "eco",
    "dod": "depth_of_discharge",
}

# Reverse lookup for async_set_modes.
LAKE6_MODE_ATTR_TO_FIELD: Final[dict[str, str]] = {
    attr: field for field, attr in LAKE6_MODE_FIELD_TO_ATTR.items()
}

# The switch entity key differs from the /modes field name (eco_mode -> eco),
# so it needs its own table instead of the reverse mapping above.
LAKE6_SWITCH_ENTITY_TO_FIELD: Final[dict[str, str]] = {
    "eco_mode": "eco",
}

# control-panels.mode is a run state rather than a setting: "1" only exists
# while a one-off run is executing, after which the device clears MI1 and
# restores the previous mode 1-4.
LAKE6_CONTROL_PANEL_MODE_IDLE: Final = "0"
LAKE6_CONTROL_PANEL_MODE_ACTIVE: Final = "1"

# MI1.time holds the start and end wall clock times joined together, which the
# device reads as UTC. A local time (UTC+8) window still returns code 200 but
# leaves mode untouched and clears MI1. V1.5.2 documents the 28 digit form, so
# that width is tried first; 24 digits only covers firmware built against V1.4
# or older, where the 28 digit form is silently dropped.
LAKE6_CONTROL_PANEL_TIME_FORMATS: Final = ("%Y%m%d%H%M%S", "%Y%m%d%H%M")

# The device flips mode to "1" asynchronously, so a read issued right after the
# POST would see its own write as missing. Wait one tick first.
LAKE6_CONTROL_PANEL_SETTLE: Final = 1

# Measured behaviour: a start time that is not earlier than the device RTC
# still returns code 200 while leaving mode at "0", even by one second. Starting
# 2 to 10 seconds in the past is always accepted, even for a 60 second window,
# and independent of the power. The window therefore begins at "now - 10 s" and
# still ends at "now + duration" so it is not shortened; earlier offsets only
# cover a device clock that runs noticeably ahead.
LAKE6_CONTROL_PANEL_START_BACKDATES: Final = (10, 60, 300)

# Three UI options -> sign of MI1.power. The protocol is the opposite of the
# usual convention: positive discharges, negative charges and zero idles.
LAKE6_MANUAL_MODE_TO_POWER_SIGN: Final[dict[str, int]] = {
    "charge": -1,
    "discharge": 1,
    "standby": 0,
}

# Dict order is the option order: charge, discharge, standby.
LAKE6_MANUAL_MODES: Final = tuple(LAKE6_MANUAL_MODE_TO_POWER_SIGN)

LAKE6_MANUAL_MODE_STANDBY: Final = "standby"

# Only these two modes use power and standby always sends 0. The power entity
# is available exactly when the selected mode is in this tuple.
LAKE6_MANUAL_POWER_MODES: Final = ("charge", "discharge")

# Standby always sends power "0", so the power field takes no part.
LAKE6_MANUAL_POWER_STANDBY: Final = 0

# Power range confirmed by the product side: 20 to 2500 W. The published
# protocol defines no range for /control-panels, and this value must not be
# reused for time-of-use, which allows 0 to 2500 W.
LAKE6_MANUAL_POWER_MIN: Final = 20
LAKE6_MANUAL_POWER_MAX: Final = 2500
LAKE6_MANUAL_POWER_STEP: Final = 1

# The duration is turned into an absolute end time on this side because the
# protocol has no such field. 1440 minutes is an integration input limit, not a
# device constraint.
LAKE6_MANUAL_DURATION_MIN: Final = 1
LAKE6_MANUAL_DURATION_MAX: Final = 1440
LAKE6_MANUAL_DURATION_STEP: Final = 1
