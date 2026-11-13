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
PLUGIN_KEYNAME = "home_assistant"
CONF_MESSAGES_PLUGIN_SETTING_ID = "messages_plugin_setting_id"
CONF_MESSAGES_VIEW_SET = "messages_view_set"
