DOMAIN = "pajgps"
VERSION = "0.8.0"

ALERT_NAMES = {1: "Shock Alert", 2: "Battery Alert", 3: "Radius Alert", 4: "SOS Alert",
               5: "Speed Alert", 6: "Power Cut-off Alert", 7: "Ignition Alert",
               9: "Drop Alert", 10: "Area Enter Alert", 11: "Area Leave Alert",
               13: "Voltage Alert", 22: "Turn off Alert"}

# Maps sensor type name → device_models[0] field that indicates hardware support.
# A value of 1 means the device model has that sensor; 0 or negative means it does not.
SENSOR_MODEL_FIELDS: dict[str, str] = {
    "voltage":  "alarm_volt",          # voltage sensor (hardware volt measurement)
    "battery":  "standalone_battery",  # standalone battery (1 = has battery, <=0 = no battery)
}

# Maps alert_type int → device_models[0] field that indicates hardware support.
# A value of 1 means the device model supports this alert type; 0 means it does not.
ALERT_TYPE_TO_MODEL_FIELD: dict[int, str] = {
    1:  "alarm_erschuetterung",   # Shock
    2:  "alarm_batteriestand",    # Battery
    4:  "alarm_sos",              # SOS
    5:  "alarm_geschwindigkeit",  # Speed
    6:  "alarm_stromunterbrechung",  # Power cut-off
    7:  "alarm_zuendalarm",       # Ignition
    9:  "alarm_drop",             # Drop
    13: "alarm_volt",             # Voltage
}

# Maps alert_type int → Device field name used in update_device() PUT payload
ALERT_TYPE_TO_DEVICE_FIELD: dict[int, str] = {
    1:  "alarmbewegung",
    2:  "alarmakkuwarnung",
    4:  "alarmsos",
    5:  "alarmgeschwindigkeit",
    6:  "alarmstromunterbrechung",
    7:  "alarmzuendalarm",
    9:  "alarm_fall_enabled",
    13: "alarm_volt",
}

# Update intervals (seconds)
DEVICES_INTERVAL = 300       # device list — rarely changes
POSITIONS_INTERVAL = 30      # positions + sensors — medium frequency
NOTIFICATIONS_INTERVAL = 10  # notifications — highest frequency

# Per-device request queue
REQUEST_DELAY = 0.2          # minimum gap between consecutive calls on the same device queue

# Elevation re-fetch guards
MIN_ELEVATION_UPDATE_DELAY = 300   # minimum seconds between elevation re-fetches per device
MIN_ELEVATION_DISTANCE = 0.0045    # ~500 m as a coordinate delta in decimal degrees
                                   # (1° latitude ≈ 111 km → 500 m ≈ 0.0045°; same value used
                                   #  for longitude as a conservative mid-latitude approximation)

ELEVATION_API_URL = "https://api.open-meteo.com/v1/elevation"