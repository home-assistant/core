"""Define possible sensor types."""

SENSOR_SMS = 'sms'
SENSOR_USAGE = 'usage'

SENSOR_UNITS = {
    SENSOR_SMS: 'unread',
    SENSOR_USAGE: 'MiB',
}

ALL = list(SENSOR_UNITS)

DEFAULT = [SENSOR_USAGE]
