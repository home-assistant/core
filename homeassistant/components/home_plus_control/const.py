"""Constants for the Legrand Home+ Control integration."""
API = "api"
CONF_SUBSCRIPTION_KEY = "subscription_key"
CONF_PLANT_UPDATE_INTERVAL = "plant_update_interval"
CONF_PLANT_TOPOLOGY_UPDATE_INTERVAL = "plant_topology_update_interval"
CONF_MODULE_STATUS_UPDATE_INTERVAL = "module_status_update_interval"

DATA_COORDINATOR = "coordinator"
DOMAIN = "home_plus_control"
ENTITY_UIDS = "entity_unique_ids"
DISPATCHER_REMOVERS = "dispatcher_removers"

# Legrand Model Identifiers - https://developer.legrand.com/documentation/product-cluster-list/#
HW_TYPE = {
    "NLC": "NLC - Cable Outlet",
    "NLF": "NLF - On-Off Dimmer Switch w/o Neutral",
    "NLP": "NLP - Socket (Connected) Outlet",
    "NLPM": "NLPM - Mobile Socket Outlet",
    "NLM": "NLM - Micromodule Switch",
    "NLV": "NLV - Shutter Switch with Neutral",
    "NLLV": "NLLV - Shutter Switch with Level Control",
    "NLL": "NLL - On-Off Toggle Switch with Neutral",
    "NLT": "NLT - Remote Switch",
    "NLD": "NLD - Double Gangs On-Off Remote Switch",
}

# Legrand OAuth2 URIs
OAUTH2_AUTHORIZE = "https://partners-login.eliotbylegrand.com/authorize"
OAUTH2_TOKEN = "https://partners-login.eliotbylegrand.com/token"

# The Legrand Home+ Control API has very limited request quotas - at the time of writing, it is
# limited to 500 calls per day (resets at 00:00) - so we want to keep updates to a minimum.
DEFAULT_UPDATE_INTERVALS = {
    # Seconds between API checks for plant information updates. This is expected to change very
    # little over time because a user's plants (homes) should rarely change.
    CONF_PLANT_UPDATE_INTERVAL: 7200,  # 120 minutes
    # Seconds between API checks for plant topology updates. This is expected to change  little
    # over time because the modules in the user's plant should be relatively stable.
    CONF_PLANT_TOPOLOGY_UPDATE_INTERVAL: 3600,  # 60 minutes
    # Seconds between API checks for module status updates. This can change frequently so we
    # check often
    CONF_MODULE_STATUS_UPDATE_INTERVAL: 300,  # 5 minutes
}

SIGNAL_ADD_ENTITIES = "home_plus_control_add_entities_signal"
