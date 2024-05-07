"""Constants for the Aladdin Connect Genie integration."""

from typing import Final

from homeassistant.components.cover import CoverEntityFeature

DOMAIN = "aladdin_genie"

OAUTH2_AUTHORIZE = "https://app.aladdinconnect.com/login.html"
OAUTH2_TOKEN = "https://twdvzuefzh.execute-api.us-east-2.amazonaws.com/v1/oauth2/token"

API_URL = "https://twdvzuefzh.execute-api.us-east-2.amazonaws.com/v1"
API_KEY = "k6QaiQmcTm2zfaNns5L1Z8duBtJmhDOW8JawlCC3"
SUPPORTED_FEATURES: Final = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
