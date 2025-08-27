"""Alexa Devices constants."""

import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "alexa_devices"
CONF_LOGIN_DATA = "login_data"

DEFAULT_DOMAIN = {"domain": "com"}
COUNTRY_DOMAINS = {
    "ar": DEFAULT_DOMAIN,
    "at": DEFAULT_DOMAIN,
    "au": {"domain": "com.au"},
    "be": {"domain": "com.be"},
    "br": DEFAULT_DOMAIN,
    "gb": {"domain": "co.uk"},
    "il": DEFAULT_DOMAIN,
    "jp": {"domain": "co.jp"},
    "mx": {"domain": "com.mx"},
    "no": DEFAULT_DOMAIN,
    "nz": {"domain": "com.au"},
    "pl": DEFAULT_DOMAIN,
    "tr": {"domain": "com.tr"},
    "us": DEFAULT_DOMAIN,
    "za": {"domain": "co.za"},
}
