"""Constants used by the Nest component."""

DOMAIN = "nest"
DATA_SDM = "sdm"

WEB_AUTH_DOMAIN = DOMAIN
INSTALLED_AUTH_DOMAIN = f"{DOMAIN}.installed"

CONF_PROJECT_ID = "project_id"
CONF_TOPIC_NAME = "topic_name"
CONF_SUBSCRIPTION_NAME = "subscription_name"
CONF_SUBSCRIBER_ID = "subscriber_id"  # Old format
CONF_SUBSCRIBER_ID_IMPORTED = "subscriber_id_imported"
CONF_CLOUD_PROJECT_ID = "cloud_project_id"

CONNECTIVITY_TRAIT_OFFLINE = "OFFLINE"

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
