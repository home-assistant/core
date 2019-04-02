"""Define possible sensor types."""

SENSOR_SMS = 'sms'
SENSOR_USAGE = 'usage'

SENSOR_UNITS = {
    SENSOR_SMS: 'unread',
    SENSOR_USAGE: 'MiB',
    'radio_quality': '%',
    'rx_level': 'dBm',
    'tx_level': 'dBm',
    'upstream': None,
    'wire_connected': None,
    'mobile_connected': None,
    'connection_text': None,
    'connection_type': None,
    'current_ps_service_type': None,
    'register_network_display': None,
    'roaming': None,
    'current_band': None,
    'cell_id': None,
}

ALL = list(SENSOR_UNITS)

DEFAULT = [SENSOR_USAGE]
