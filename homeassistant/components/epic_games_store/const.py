"""Constants for the Epic Games Store integration."""

from enum import StrEnum

DOMAIN = "epic_games_store"

SUPPORTED_LANGUAGES = [
    "ar",
    "de",
    "en-US",
    "es-ES",
    "es-MX",
    "fr",
    "it",
    "ja",
    "ko",
    "pl",
    "pt-BR",
    "ru",
    "th",
    "tr",
    "zh-CN",
    "zh-Hant",
]


class CalendarType(StrEnum):
    """Calendar types."""

    FREE = "free"
    DISCOUNT = "discount"
