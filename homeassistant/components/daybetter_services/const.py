"""Constants for the DayBetter Services integration."""

DOMAIN = "daybetter_services"

# API constants
API_BASE_URL = "https://a.dbiot.org/daybetter/hass/api/v1.0/"

# Config flow constants
CONF_NAME = "name"
CONF_ENTITY_ID = "entity_id"

# Default values
DEFAULT_NAME = "DayBetter Service"

# Update interval
UPDATE_INTERVAL = 60  # seconds

CONF_USER_CODE = "user_code"
CONF_TOKEN = "token"

# MQTT Certificate constants
CERT_BROKER = "cert_broker"
CERT_CLIENT_ID = "cert_client_id"
CERT_CA_CERT = "cert_ca_cert"
CERT_CLIENT_CERT = "cert_client_cert"
CERT_CLIENT_KEY = "cert_client_key"

# Platforms supported by this integration
PLATFORMS = ["light", "sensor", "switch"]
