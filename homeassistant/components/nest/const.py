"""Constants used by the Nest component."""

DOMAIN = "nest"
DATA_SDM = "sdm"
DATA_SUBSCRIBER = "subscriber"
DATA_NEST_CONFIG = "nest_config"

CONF_PROJECT_ID = "project_id"
CONF_SUBSCRIBER_ID = "subscriber_id"

SIGNAL_NEST_UPDATE = "nest_update"

# For the Google Nest Device Access API
OAUTH2_AUTHORIZE = (
    "https://nestservices.google.com/partnerconnections/{project_id}/auth"
)
OAUTH2_TOKEN = "https://www.googleapis.com/oauth2/v4/token"
SDM_SCOPES = [
    "https://www.googleapis.com/auth/sdm.service",
    "https://www.googleapis.com/auth/pubsub",
]
API_URL = "https://smartdevicemanagement.googleapis.com/v1"
OOB_REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
