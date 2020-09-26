"""Constants for the nest integration."""

DOMAIN = "google_sdm"

OAUTH2_AUTHORIZE_TEMPLATE = "https://nestservices.google.com/partnerconnections/{}/auth"
OAUTH2_SCOPE = "https://www.googleapis.com/auth/sdm.service"
OAUTH2_PROMPT = "consent"
OAUTH2_ACCESS_TYPE = "offline"
OAUTH2_TOKEN = "https://www.googleapis.com/oauth2/v4/token"

DATA_CONFIG = "config"
DATA_DEVICES = "devices"

CONF_SERVICE_ACCOUNT = "service_account"
CONF_CLIENT_EMAIL = "client_email"
CONF_PROJECT_ID = "project_id"
CONF_PRIVATE_KEY = "private_key"
CONF_SUBSCRIPTION = "subscription"
