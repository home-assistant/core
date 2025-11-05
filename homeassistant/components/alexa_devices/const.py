"""Alexa Devices constants."""

import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "alexa_devices"
CONF_LOGIN_DATA = "login_data"
CONF_SITE = "site"

DEFAULT_DOMAIN = "com"
COUNTRY_DOMAINS = {
    "ar": DEFAULT_DOMAIN,
    "at": DEFAULT_DOMAIN,
    "au": "com.au",
    "be": "com.be",
    "br": DEFAULT_DOMAIN,
    "gb": "co.uk",
    "il": DEFAULT_DOMAIN,
    "jp": "co.jp",
    "mx": "com.mx",
    "no": DEFAULT_DOMAIN,
    "nz": "com.au",
    "pl": DEFAULT_DOMAIN,
    "tr": "com.tr",
    "us": DEFAULT_DOMAIN,
    "za": "co.za",
}

CATEGORY_SENSORS = "sensors"
CATEGORY_NOTIFICATIONS = "notifications"
