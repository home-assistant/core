"""Define possible sensor types."""

SENSOR_SMS = 'sms'
SENSOR_USAGE = 'usage'

SENSOR_UNITS = {
    SENSOR_SMS: 'unread',
    SENSOR_USAGE: 'MiB',
}

ALL = SENSOR_UNITS.keys()

DEFAULT = [SENSOR_USAGE]
