"""Helpers for cookidoo."""

from cookidoo_api import CookidooLocalizationConfig

from .const import LOCALIZATION_SPLIT_CHAR


def cookidoo_localization_for_key(
    localizations: list[CookidooLocalizationConfig], key: str
) -> CookidooLocalizationConfig:
    """Get a cookidoo localization config for the config key."""
    country_code, language = key.split(LOCALIZATION_SPLIT_CHAR)
    return next(
        localization
        for localization in localizations
        if localization["country_code"].lower() == country_code
        and localization["language"].lower() == language
    )
