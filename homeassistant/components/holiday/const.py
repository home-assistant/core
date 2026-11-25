"""Constants for the Holiday integration."""

from typing import Final

DOMAIN: Final = "holiday"

CONF_PROVINCE: Final = "province"
CONF_CATEGORIES: Final = "categories"
CONF_HINDU_SHOW_ESTIMATED: Final = "hindu_show_estimated"
CONF_INCLUDE_SUNDAYS: Final = "include_sundays"
CONF_ISLAMIC_SHOW_ESTIMATED: Final = "islamic_show_estimated"

# Country specific options of the holidays library that can be configured
COUNTRY_OPTIONS: Final = [
    CONF_INCLUDE_SUNDAYS,
    CONF_ISLAMIC_SHOW_ESTIMATED,
    CONF_HINDU_SHOW_ESTIMATED,
]

ISSUE_UNSUPPORTED_COUNTRY: Final = "unsupported_country"
ISSUE_UNSUPPORTED_PROVINCE: Final = "unsupported_province"
ISSUE_UNSUPPORTED_CATEGORIES: Final = "unsupported_categories"
