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

# Google-hosted Pub/Sub topics stop receiving events after November 30, 2026
LEGACY_TOPIC_PREFIX = "projects/sdm-"
LEGACY_TOPIC_ISSUE_ID = "legacy_pubsub_topic_{entry_id}"
SUBSCRIPTION_NOT_FOUND_ISSUE_ID = "pubsub_subscription_not_found_{entry_id}"
PUBSUB_LEARN_MORE_URL = (
    "https://developers.google.com/nest/device-access/subscribe-to-events"
)

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
