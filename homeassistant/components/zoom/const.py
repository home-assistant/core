"""Constants for the Zoom integration."""
import voluptuous as vol

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers.config_validation import string

UNSUB = "unsub"
API = "api"
DOMAIN = "zoom"
DEFAULT_NAME = "Zoom"

HA_URL = f"/api/{DOMAIN}"

CONF_VERIFICATION_TOKEN = "verification_token"

OAUTH2_AUTHORIZE = "https://zoom.us/oauth/authorize"
OAUTH2_TOKEN = "https://zoom.us/oauth/token"

BASE_URL = "https://api.zoom.us/v2/"
USER_PROFILE_URL = "users/me"
CONTACT_LIST_URL = "chat/users/me/contacts"

ZOOM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): vol.Coerce(str),
        vol.Required(CONF_CLIENT_SECRET): vol.Coerce(str),
        vol.Optional(CONF_VERIFICATION_TOKEN): vol.Coerce(str),
    }
)

ATTR_EVENT = "event"
ATTR_PAYLOAD = "payload"
ATTR_OBJECT = "object"
ATTR_ID = "id"
ATTR_CONNECTIVITY_STATUS = "presence_status"

CONNECTIVITY_EVENT = "user.presence_status_updated"
CONNECTIVITY_STATUS = [ATTR_PAYLOAD, ATTR_OBJECT, ATTR_CONNECTIVITY_STATUS]
CONNECTIVITY_ID = [ATTR_PAYLOAD, ATTR_OBJECT, ATTR_ID]
CONNECTIVITY_STATUS_ON = "Do_Not_Disturb"

HA_ZOOM_EVENT = f"{DOMAIN}_webhook"

WEBHOOK_RESPONSE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_EVENT): string, vol.Required(ATTR_PAYLOAD): dict}
)
