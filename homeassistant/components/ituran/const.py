"""Constants for the Ituran integration."""

from datetime import timedelta
from typing import Final

DOMAIN = "ituran"

CONF_ID_OR_PASSPORT: Final = "id_or_passport"
CONF_PHONE_NUMBER: Final = "phone_number"
CONF_MOBILE_ID: Final = "mobile_id"
CONF_OTP: Final = "otp"

UPDATE_INTERVAL = timedelta(seconds=300)
