"""Constants for the Ekey Bionyx integration."""

import logging

DOMAIN = "ekeybionyx"
INTEGRATION_NAME = "ekey bionyx"

LOGGER = logging.getLogger(__package__)

OAUTH2_AUTHORIZE = "https://ekeybionyxprod.b2clogin.com/ekeybionyxprod.onmicrosoft.com/B2C_1_sign_in_v2/oauth2/v2.0/authorize"
OAUTH2_TOKEN = "https://ekeybionyxprod.b2clogin.com/ekeybionyxprod.onmicrosoft.com/B2C_1_sign_in_v2/oauth2/v2.0/token"
API_URL = "https://api.bionyx.io/3rd-party/api"
SCOPE = "https://ekeybionyxprod.onmicrosoft.com/3rd-party-api/api-access"
