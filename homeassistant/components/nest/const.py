"""Constants used by the Nest component."""

from typing import Final

DOMAIN: Final = "nest"
DATA_SDM: Final = "sdm"
DATA_SUBSCRIBER: Final = "subscriber"

SIGNAL_NEST_UPDATE: Final = "nest_update"

# For the Google Nest Device Access API
OAUTH2_AUTHORIZE: Final = (
    "https://nestservices.google.com/partnerconnections/{project_id}/auth"
)
OAUTH2_TOKEN: Final = "https://www.googleapis.com/oauth2/v4/token"
SDM_SCOPES: Final = [
    "https://www.googleapis.com/auth/sdm.service",
    "https://www.googleapis.com/auth/pubsub",
]
API_URL: Final = "https://smartdevicemanagement.googleapis.com/v1"
OOB_REDIRECT_URI: Final = "urn:ietf:wg:oauth:2.0:oob"

SERVICE_SNAPSHOT_EVENT: Final = "snapshot_event"
