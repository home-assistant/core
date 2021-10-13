"""Constants for the ThingBits integration."""

DOMAIN = "thingbits"
LOCAL_ADDRESS = "thingbits.local"
LOCAL_TOPIC = "thingbits/sensors"
CLOUD_ADDRESS = "mqtt.thingbits.com"
CLOUD_TOPIC = "sensors"
UDP_PORT = 25968
SENSOR_NAMES = {
    "Beacon": "Beacon",
    "Button": "Push Button",
    "Toggle": "Toggle Button",
    "Tilt": "Tilt",
    "Reed": "Reed",
    "Shake": "Shake",
    "Motion": "Motion",
    "Knock": "Knock",
    "T,RH": "Temp. / Rel. Humidity",
    "Light": "Light",
    "Sound": "Sound",
    "Leak": "Leak",
    "Temp": "Temperature",
    "DUMMY": "Dummy",
}
