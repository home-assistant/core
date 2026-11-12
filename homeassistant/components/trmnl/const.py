"""Constants for the TRMNL integration."""

import logging

DOMAIN = "trmnl"

LOGGER = logging.getLogger(__package__)

OAUTH2_AUTHORIZE = "https://trmnl.com/oidc/authorize"
OAUTH2_TOKEN = "https://trmnl.com/oidc/token"
# A public client: TRMNL registered it with no secret, and PKCE protects the code.
CLIENT_ID = "home-assistant"
OAUTH2_SCOPES = "openid profile read devices content delete"
# The consent page lets the user untick any scope; without these the devices cannot load.
REQUIRED_SCOPES = {"read", "devices"}
