"""Test the Google Assistant SDK helpers."""
from homeassistant.components.google_assistant_sdk.const import SUPPORTED_LANGUAGE_CODES
from homeassistant.components.google_assistant_sdk.helpers import (
    DEFAULT_LANGUAGE_CODES,
    default_language_code,
)
from homeassistant.core import HomeAssistant


def test_default_language_codes(hass: HomeAssistant) -> None:
    """Test all supported languages have a default language_code."""
    for language_code in SUPPORTED_LANGUAGE_CODES:
        lang = language_code.split("-", maxsplit=1)[0]
        assert DEFAULT_LANGUAGE_CODES.get(lang)


def test_default_language_code(hass: HomeAssistant) -> None:
    """Test default_language_code."""
    assert default_language_code(hass) == "en-US"

    hass.config.language = "en"
    hass.config.country = "US"
    assert default_language_code(hass) == "en-US"

    hass.config.language = "en"
    hass.config.country = "GB"
    assert default_language_code(hass) == "en-GB"

    hass.config.language = "en"
    hass.config.country = "ES"
    assert default_language_code(hass) == "en-US"

    hass.config.language = "es"
    hass.config.country = "ES"
    assert default_language_code(hass) == "es-ES"

    hass.config.language = "es"
    hass.config.country = "MX"
    assert default_language_code(hass) == "es-MX"

    hass.config.language = "es"
    hass.config.country = None
    assert default_language_code(hass) == "es-ES"

    hass.config.language = "el"
    hass.config.country = "GR"
    assert default_language_code(hass) == "en-US"
