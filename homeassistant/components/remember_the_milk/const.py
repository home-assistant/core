import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
from homeassistant.helpers import config_validation as cv

DOMAIN = "remember_the_milk"
CONF_SHARED_SECRET = "shared_secret"
RTM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SHARED_SECRET): cv.string,
    }
)
RTM_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Optional("dummy_field"): cv.string,
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [RTM_SCHEMA])}, extra=vol.ALLOW_EXTRA
)
CONF_ID_MAP = "id_map"
CONF_LIST_ID = "list_id"
CONF_TIMESERIES_ID = "timeseries_id"
CONF_TASK_ID = "task_id"

SERVICE_SCHEMA_CREATE_TASK = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Optional(CONF_ID): cv.string}
)
SERVICE_SCHEMA_COMPLETE_TASK = vol.Schema({vol.Required(CONF_ID): cv.string})
