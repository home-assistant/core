"""Constants for the Renault component."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "renault"

CONF_KAMEREON_ACCOUNT_ID = "kamereon_account_id"

GIGYA_KEY = "xxx"
GIGYA_URL = "https://accounts.eu1.gigya.com"
KAMEREON_KEY = "xxx"
KAMEREON_URL = "https://api-wired-prod-1-euw1.wrd-aws.com"

SUPPORTED_PLATFORMS = [
    "sensor",
]
