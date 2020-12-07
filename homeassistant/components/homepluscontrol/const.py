"""Constants for the Legrand Home+ Control integration."""
CONF_SUBSCRIPTION_KEY = "subscription_key"
CONF_REDIRECT_URI = "redirect_uri"

DOMAIN = "homepluscontrol"

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
PLANT_URL = "https://api.developer.legrand.com/hc/api/v1.0/plants"
