"""Constants for the TRMNL integration."""

import logging

DOMAIN = "trmnl"

LOGGER = logging.getLogger(__package__)

OAUTH2_AUTHORIZE = "https://trmnl.com/oidc/authorize"
OAUTH2_TOKEN = "https://trmnl.com/oidc/token"
OAUTH2_REVOKE = "https://trmnl.com/oidc/revoke"
CLIENT_ID = "home-assistant"
OAUTH2_SCOPES = "openid profile read devices content delete"
REQUIRED_SCOPES = {"read", "devices"}

CONF_HOME_ENTITIES = "home_entities"
CONF_HOME_PLUGIN_SETTING_ID = "home_plugin_setting_id"
# QUESTION: TRMNL's id for its Homey plugin; replace with a keyname lookup once the API takes one.
HOMEY_PLUGIN_ID = 95
PRIVATE_PLUGIN_ID = 37
CONF_MESSAGES_PLUGIN_SETTING_ID = "messages_plugin_setting_id"
CONF_MESSAGES_PLUGIN_SETTING_READY = "messages_plugin_setting_ready"
