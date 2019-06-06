"""Constants in Logi Circle component."""

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_API_KEY = 'api_key'
CONF_REDIRECT_URI = 'redirect_uri'

DEFAULT_CACHEDB = '.logi_cache.pickle'

DOMAIN = 'logi_circle'
DATA_LOGI = DOMAIN

LED_MODE_KEY = 'LED'
RECORDING_MODE_KEY = 'RECORDING_MODE'

# Sensor types: Name, unit of measure, icon per sensor key.
LOGI_SENSORS = {
    'battery_level': [
        'Battery', '%', 'battery-50'],

    'last_activity_time': [
        "Last Activity", None, 'history'],

    'recording': [
        'Recording Mode', None, 'eye'],

    'signal_strength_category': [
        "WiFi Signal Category", None, 'wifi'],

    'signal_strength_percentage': [
        "WiFi Signal Strength", '%', 'wifi'],

    'streaming': [
        'Streaming Mode', None, 'camera'],
}

SIGNAL_LOGI_CIRCLE_RECONFIGURE = 'logi_circle_reconfigure'
SIGNAL_LOGI_CIRCLE_SNAPSHOT = 'logi_circle_snapshot'
SIGNAL_LOGI_CIRCLE_RECORD = 'logi_circle_record'

# Attribution
ATTRIBUTION = "Data provided by circle.logi.com"
DEVICE_BRAND = 'Logitech'
