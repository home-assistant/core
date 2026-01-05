"""Constants for the Aladdin Connect Genie integration."""

from typing import Final

from homeassistant.components.cover import CoverEntityFeature

DOMAIN = "aladdin_connect"
CONFIG_FLOW_VERSION = 2
CONFIG_FLOW_MINOR_VERSION = 1

OAUTH2_AUTHORIZE = "https://app.aladdinconnect.com/login.html"
OAUTH2_TOKEN = "https://twdvzuefzh.execute-api.us-east-2.amazonaws.com/v1/oauth2/token"

SUPPORTED_FEATURES: Final = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
