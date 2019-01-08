"""Constants in Logi Circle component."""

# Domain
DOMAIN = 'logi_circle'
DATA_LOGI = DOMAIN
DEFAULT_NAME = DOMAIN

# Config props
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_API_KEY = 'api_key'
CONF_REDIRECT_URI = 'redirect_uri'

# Activity dict
ACTIVITY_PROP = 'activity'
ACTIVITY_ID = 'activity_id'
ACTIVITY_RELEVANCE = 'relevance_level'
ACTIVITY_START_TIME = 'start_time'
ACTIVITY_DURATION = 'duration'
ACTIVITY_BASE = {
    'activity_id': None,
    'relevance_level': None,
    'start_time': None,
    'duration': None
}

# Event handling
SIGNAL_LOGI_CIRCLE_UPDATE = 'logi_circle_update'

# Polling props
POLL_PROPS = ['battery_level',
              'signal_strength_category',
              'signal_strength_percentage']

# Attribution
CONF_ATTRIBUTION = "Data provided by circle.logi.com"
