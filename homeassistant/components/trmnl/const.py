"""Constants for the TRMNL integration."""

import logging

DOMAIN = "trmnl"

LOGGER = logging.getLogger(__package__)

OAUTH2_AUTHORIZE = "https://trmnl.com/oidc/authorize"
OAUTH2_TOKEN = "https://trmnl.com/oidc/token"
CLIENT_ID = "home-assistant"
OAUTH2_SCOPES = "openid profile read devices content delete"
REQUIRED_SCOPES = {"read", "devices"}
