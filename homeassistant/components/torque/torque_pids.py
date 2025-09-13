"""PID definitions for the Torque integration."""

from homeassistant.const import ATTR_ICON, ATTR_NAME, ATTR_UNIT_OF_MEASUREMENT, DEGREE

PIDS_INFO = {
    0x00: {
        ATTR_NAME: "Engine RPM",
        ATTR_UNIT_OF_MEASUREMENT: "rpm",
        ATTR_ICON: "mdi:speedometer",
    },
    0x04: {
        ATTR_NAME: "Engine Load",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:engine",
    },
    0x05: {
        ATTR_NAME: "Engine Coolant Temperature",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:thermometer",
    },
    0x06: {
        ATTR_NAME: "Short Term Fuel Trim Bank 1",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:fuel",
    },
    0x07: {
        ATTR_NAME: "Long Term Fuel Trim Bank 1",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:fuel",
    },
    0x08: {
        ATTR_NAME: "Short Term Fuel Trim Bank 2",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:fuel",
    },
    0x09: {
        ATTR_NAME: "Long Term Fuel Trim Bank 2",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:fuel",
    },
    0x0A: {
        ATTR_NAME: "Fuel Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_ICON: "mdi:car-cruise-control",
    },
    0x0B: {
        ATTR_NAME: "Intake Manifold Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_ICON: "mdi:car-turbocharger",
    },
    0x0C: {
        ATTR_NAME: "Vehicle Speed",
        ATTR_UNIT_OF_MEASUREMENT: "km/h",
        ATTR_ICON: "mdi:speedometer",
    },
    0x0D: {
        ATTR_NAME: "Timing Advance",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:timer",
    },
    0x0E: {
        ATTR_NAME: "Intake Air Temperature",
        ATTR_UNIT_OF_MEASUREMENT: "°C",
        ATTR_ICON: "mdi:thermometer",
    },
    0x0F: {
        ATTR_NAME: "Air Flow Rate",
        ATTR_UNIT_OF_MEASUREMENT: "g/s",
        ATTR_ICON: "mdi:weather-windy",
    },
    0x10: {
        ATTR_NAME: "Throttle Position",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:car-cruise-control",
    },
    0x11: {
        ATTR_NAME: "Secondary Air Status",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:fan",
    },
    0x1C: {
        ATTR_NAME: "OBD Standard",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:car-info",
    },
    0x21: {
        ATTR_NAME: "Distance Traveled with MIL On",
        ATTR_UNIT_OF_MEASUREMENT: "km",
        ATTR_ICON: "mdi:counter",
    },
    0x23: {
        ATTR_NAME: "Fuel Rail Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_ICON: "mdi:fuel",
    },
    0x2F: {
        ATTR_NAME: "Fuel Level Input",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:gas-station",
    },
    0x30: {
        ATTR_NAME: "Warm-ups Since Codes Cleared",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:counter",
    },
    0x31: {
        ATTR_NAME: "Distance Traveled Since Codes Cleared",
        ATTR_UNIT_OF_MEASUREMENT: "km",
        ATTR_ICON: "mdi:counter",
    },
    0x33: {
        ATTR_NAME: "Barometric Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_ICON: "mdi:weather-cloudy",
    },
    0x42: {
        ATTR_NAME: "Control Module Voltage",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:battery",
    },
    0x43: {
        ATTR_NAME: "Absolute Load Value",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:engine",
    },
    0x44: {
        ATTR_NAME: "Commanded Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x45: {
        ATTR_NAME: "Relative Throttle Position",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:car-cruise-control",
    },
    0x46: {
        ATTR_NAME: "Ambient Air Temperature",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:thermometer",
    },
    0x47: {
        ATTR_NAME: "Absolute Throttle Position B",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:car-cruise-control",
    },
    0x49: {
        ATTR_NAME: "Accelerator Pedal Position D",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:pedal-accelerator",
    },
    0x4A: {
        ATTR_NAME: "Accelerator Pedal Position E",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:pedal-accelerator",
    },
    0x4F: {
        ATTR_NAME: "Maximum Value for Fuel-Air Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x52: {
        ATTR_NAME: "Ethanol Fuel %",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:fuel",
    },
    0x5C: {
        ATTR_NAME: "Engine Oil Temperature",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:oil-temperature",
    },
    0x5E: {
        ATTR_NAME: "Engine Fuel Rate",
        ATTR_UNIT_OF_MEASUREMENT: "L/h",
        ATTR_ICON: "mdi:fuel",
    },
    # Torque custom PIDs
    "ff1001": {
        ATTR_NAME: "Vehicle Speed",
        ATTR_UNIT_OF_MEASUREMENT: "km/h",
        ATTR_ICON: "mdi:speedometer",
    },
    "ff1005": {
        ATTR_NAME: "GPS Longitude",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:map-marker",
    },
    "ff1006": {
        ATTR_NAME: "GPS Latitude",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:map-marker",
    },
    "ff1007": {
        ATTR_NAME: "GPS Altitude",
        ATTR_UNIT_OF_MEASUREMENT: "m",
        ATTR_ICON: "mdi:image-filter-hdr",
    },
    "ff1010": {
        ATTR_NAME: "GPS Speed (Meters/second)",
        ATTR_UNIT_OF_MEASUREMENT: "m/s",
        ATTR_ICON: "mdi:speedometer",
    },
    "ff1014": {
        ATTR_NAME: "Battery Voltage",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:battery",
    },
    "ff1208": {
        ATTR_NAME: "Trip average consumption",
        ATTR_UNIT_OF_MEASUREMENT: "l/100km",
        ATTR_ICON: "mdi:fuel",
    },
    "ff1226": {
        ATTR_NAME: "Ambient Temperature",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:thermometer",
    },
    "ff120c": {
        ATTR_NAME: "Trip Distance",
        ATTR_UNIT_OF_MEASUREMENT: "km",
        ATTR_ICON: "mdi:map-marker-distance",
    },
    "ff1237": {
        ATTR_NAME: "Fuel Cost",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:currency-usd",
    },
    "ff1249": {
        ATTR_NAME: "Trip Time",
        ATTR_UNIT_OF_MEASUREMENT: "min",
        ATTR_ICON: "mdi:clock",
    },
    0x03: {
        ATTR_NAME: "Fuel System Status",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:fuel",
    },
    0x12: {
        ATTR_NAME: "Oxygen Sensors Present",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x13: {
        ATTR_NAME: "Oxygen Sensor 1",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x14: {
        ATTR_NAME: "Oxygen Sensor 2",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x15: {
        ATTR_NAME: "Oxygen Sensor 3",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x16: {
        ATTR_NAME: "Oxygen Sensor 4",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x17: {
        ATTR_NAME: "Oxygen Sensor 5",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x18: {
        ATTR_NAME: "Oxygen Sensor 6",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x19: {
        ATTR_NAME: "Oxygen Sensor 7",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x1A: {
        ATTR_NAME: "Oxygen Sensor 8",
        ATTR_UNIT_OF_MEASUREMENT: "V",
        ATTR_ICON: "mdi:chart-bubble",
    },
    0x1F: {
        ATTR_NAME: "Run Time Since Engine Start",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:timer",
    },
    0x24: {
        ATTR_NAME: "O2 Sensor 1 Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x25: {
        ATTR_NAME: "O2 Sensor 2 Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x26: {
        ATTR_NAME: "O2 Sensor 3 Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x27: {
        ATTR_NAME: "O2 Sensor 4 Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x28: {
        ATTR_NAME: "O2 Sensor 5 Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x29: {
        ATTR_NAME: "O2 Sensor 6 Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x2A: {
        ATTR_NAME: "O2 Sensor 7 Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x2B: {
        ATTR_NAME: "O2 Sensor 8 Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x2C: {
        ATTR_NAME: "EGR Error",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:engine",
    },
    0x2D: {
        ATTR_NAME: "Evaporative Purge",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:air-filter",
    },
    0x2E: {
        ATTR_NAME: "Fuel Level Input",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:gas-station",
    },
    0x32: {
        ATTR_NAME: "Evap System Vapor Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "Pa",
        ATTR_ICON: "mdi:gauge",
    },
    0x34: {
        ATTR_NAME: "O2 Sensor 1 Wide-range Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x35: {
        ATTR_NAME: "O2 Sensor 2 Wide-range Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x36: {
        ATTR_NAME: "O2 Sensor 3 Wide-range Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x37: {
        ATTR_NAME: "O2 Sensor 4 Wide-range Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x38: {
        ATTR_NAME: "O2 Sensor 5 Wide-range Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x39: {
        ATTR_NAME: "O2 Sensor 6 Wide-range Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x3A: {
        ATTR_NAME: "O2 Sensor 7 Wide-range Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x3B: {
        ATTR_NAME: "O2 Sensor 8 Wide-range Equivalence Ratio",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:lambda",
    },
    0x3C: {
        ATTR_NAME: "Catalyst Temperature Bank 1 Sensor 1",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:thermometer",
    },
    0x3D: {
        ATTR_NAME: "Catalyst Temperature Bank 2 Sensor 1",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:thermometer",
    },
    0x3E: {
        ATTR_NAME: "Catalyst Temperature Bank 1 Sensor 2",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:thermometer",
    },
    0x3F: {
        ATTR_NAME: "Catalyst Temperature Bank 2 Sensor 2",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:thermometer",
    },
    0x41: {
        ATTR_NAME: "Monitor Status This Drive Cycle",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:check",
    },
    0x48: {
        ATTR_NAME: "Absolute Throttle Position C",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:car-cruise-control",
    },
    0x4B: {
        ATTR_NAME: "Accelerator Pedal Position F",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:pedal-accelerator",
    },
    0x4C: {
        ATTR_NAME: "Commanded Throttle Actuator",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:car-cruise-control",
    },
    0x50: {
        ATTR_NAME: "Maximum Value for Air Flow Rate",
        ATTR_UNIT_OF_MEASUREMENT: "g/s",
        ATTR_ICON: "mdi:weather-windy",
    },
    0x51: {
        ATTR_NAME: "Fuel Type",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:fuel",
    },
    0x53: {
        ATTR_NAME: "Absolute Evap System Vapor Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_ICON: "mdi:gauge",
    },
    0x54: {
        ATTR_NAME: "Evap System Vapor Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "Pa",
        ATTR_ICON: "mdi:gauge",
    },
    0x55: {
        ATTR_NAME: "Short Term Secondary Oxygen Sensor Trim Bank 1",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:lambda",
    },
    0x56: {
        ATTR_NAME: "Long Term Secondary Oxygen Sensor Trim Bank 1",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:lambda",
    },
    0x57: {
        ATTR_NAME: "Short Term Secondary Oxygen Sensor Trim Bank 2",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:lambda",
    },
    0x58: {
        ATTR_NAME: "Long Term Secondary Oxygen Sensor Trim Bank 2",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:lambda",
    },
    0x59: {
        ATTR_NAME: "Fuel Rail Absolute Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_ICON: "mdi:fuel",
    },
    0x5A: {
        ATTR_NAME: "Relative Accelerator Pedal Position",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:pedal-accelerator",
    },
    0x5B: {
        ATTR_NAME: "Hybrid Battery Pack Remaining Life",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:battery",
    },
    0x5D: {
        ATTR_NAME: "Fuel Injection Timing",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:timer",
    },
    "ff1002": {
        ATTR_NAME: "Engine Load",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:engine",
    },
    "ff1003": {
        ATTR_NAME: "Engine Coolant Temperature",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:thermometer",
    },
    "ff1004": {
        ATTR_NAME: "Fuel Level",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:gas-station",
    },
    "ff1008": {
        ATTR_NAME: "GPS Bearing",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:compass",
    },
    "ff1009": {
        ATTR_NAME: "GPS Accuracy",
        ATTR_UNIT_OF_MEASUREMENT: "m",
        ATTR_ICON: "mdi:map-marker-radius",
    },
    "ff100A": {
        ATTR_NAME: "GPS Satellites",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:satellite-variant",
    },
    "ff100B": {
        ATTR_NAME: "GPS PDOP",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:satellite-variant",
    },
    "ff100C": {
        ATTR_NAME: "GPS HDOP",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:satellite-variant",
    },
    "ff100D": {
        ATTR_NAME: "GPS VDOP",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:satellite-variant",
    },
    "ff100E": {
        ATTR_NAME: "Barometric Pressure",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_ICON: "mdi:weather-cloudy",
    },
    "ff100F": {
        ATTR_NAME: "GPS Speed (km/h)",
        ATTR_UNIT_OF_MEASUREMENT: "km/h",
        ATTR_ICON: "mdi:speedometer",
    },
    "ff1011": {
        ATTR_NAME: "Current Trip Distance",
        ATTR_UNIT_OF_MEASUREMENT: "km",
        ATTR_ICON: "mdi:map-marker-distance",
    },
    "ff1012": {
        ATTR_NAME: "Current Trip Time",
        ATTR_UNIT_OF_MEASUREMENT: "min",
        ATTR_ICON: "mdi:clock",
    },
    "ff1013": {
        ATTR_NAME: "Volumetric Efficiency",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ICON: "mdi:engine",
    },
    "ff1020": {
        ATTR_NAME: "0-60 mph Time",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:timer",
    },
    "ff1021": {
        ATTR_NAME: "0-100 kph Time",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:timer",
    },
    "ff1022": {
        ATTR_NAME: "1/4 Mile Time",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:timer",
    },
    "ff1023": {
        ATTR_NAME: "1/4 Mile End Speed",
        ATTR_UNIT_OF_MEASUREMENT: "km/h",
        ATTR_ICON: "mdi:speedometer",
    },
    "ff1024": {
        ATTR_NAME: "0-200m Time",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:timer",
    },
    "ff1025": {
        ATTR_NAME: "0-200m End Speed",
        ATTR_UNIT_OF_MEASUREMENT: "km/h",
        ATTR_ICON: "mdi:speedometer",
    },
    "ff1026": {
        ATTR_NAME: "60-80 mph Time",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:timer",
    },
    "ff1027": {
        ATTR_NAME: "60-130 mph Time",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:timer",
    },
    "ff1028": {
        ATTR_NAME: "0-30 mph Time",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:timer",
    },
    "ff1206": {
        ATTR_NAME: "Trip Average KPL",
        ATTR_UNIT_OF_MEASUREMENT: "km/l",
        ATTR_ICON: "mdi:fuel",
    },
    "ff1207": {
        ATTR_NAME: "Trip Average MPG",
        ATTR_UNIT_OF_MEASUREMENT: "mpg",
        ATTR_ICON: "mdi:fuel",
    },
    "ff1210": {
        ATTR_NAME: "Trip Distance (GPS)",
        ATTR_UNIT_OF_MEASUREMENT: "km",
        ATTR_ICON: "mdi:map-marker-distance",
    },
    "ff1211": {
        ATTR_NAME: "Trip Odometer",
        ATTR_UNIT_OF_MEASUREMENT: "km",
        ATTR_ICON: "mdi:counter",
    },
    "ff1212": {
        ATTR_NAME: "Trip Time (s)",
        ATTR_UNIT_OF_MEASUREMENT: "s",
        ATTR_ICON: "mdi:clock",
    },
    "ff1218": {
        ATTR_NAME: "Acceleration Sensor X-axis",
        ATTR_UNIT_OF_MEASUREMENT: "g",
        ATTR_ICON: "mdi:axis-x-arrow",
    },
    "ff1219": {
        ATTR_NAME: "Acceleration Sensor Y-axis",
        ATTR_UNIT_OF_MEASUREMENT: "g",
        ATTR_ICON: "mdi:axis-y-arrow",
    },
    "ff121A": {
        ATTR_NAME: "Acceleration Sensor Z-axis",
        ATTR_UNIT_OF_MEASUREMENT: "g",
        ATTR_ICON: "mdi:axis-z-arrow",
    },
    "ff121B": {
        ATTR_NAME: "Acceleration Sensor Total",
        ATTR_UNIT_OF_MEASUREMENT: "g",
        ATTR_ICON: "mdi:speedometer",
    },
    "ff121C": {
        ATTR_NAME: "CO2 Emission",
        ATTR_UNIT_OF_MEASUREMENT: "kg/km",
        ATTR_ICON: "mdi:molecule-co2",
    },
    "ff1238": {
        ATTR_NAME: "Average Fuel Cost",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:currency-usd",
    },
    "ff1239": {
        ATTR_NAME: "Engine kW",
        ATTR_UNIT_OF_MEASUREMENT: "kW",
        ATTR_ICON: "mdi:engine",
    },
    "ff123A": {
        ATTR_NAME: "Engine HP",
        ATTR_UNIT_OF_MEASUREMENT: "hp",
        ATTR_ICON: "mdi:engine",
    },
    "ff1240": {
        ATTR_NAME: "Current Gear",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ICON: "mdi:cog",
    },
    "ff1266": {
        ATTR_NAME: "Trip Time (Since journey start)",
        ATTR_UNIT_OF_MEASUREMENT: "min",
        ATTR_ICON: "mdi:clock",
    },
    "ff123b": {
        ATTR_NAME: "GPS Bearing",
        ATTR_UNIT_OF_MEASUREMENT: DEGREE,
        ATTR_ICON: "mdi:compass",
    },
    "ff1204": {
        ATTR_NAME: "Trip Distance",
        ATTR_UNIT_OF_MEASUREMENT: "km",
        ATTR_ICON: "mdi:map-marker-distance",
    },
}
