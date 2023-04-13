"""Test Home Assistant language util methods."""
from __future__ import annotations

from homeassistant.util import language


def test_region_match() -> None:
    """Test that an exact language/region match is preferred."""
    assert language.matches("en-GB", ["fr-Fr", "en-US", "en-GB"]) == [
        "en-GB",
        "en-US",
    ]


def test_no_match() -> None:
    """Test that an empty list is returned when there is no match."""
    assert (
        language.matches(
            "en-US",
            ["de-DE", "fr-FR", "zh"],
        )
        == []
    )

    assert (
        language.matches(
            "en",
            ["de-DE", "fr-FR", "zh"],
        )
        == []
    )

    assert language.matches("en", []) == []


def test_prefer_us_english() -> None:
    """Test that U.S. English is preferred when no region is provided."""
    assert language.matches("en", ["en-GB", "en-US", "fr-FR"]) == [
        "en-US",
        "en-GB",
    ]


def test_country_preferred() -> None:
    """Test that country hint disambiguates."""
    assert language.matches(
        "en",
        ["fr-Fr", "en-US", "en-GB"],
        country="GB",
    ) == [
        "en-GB",
        "en-US",
    ]


def test_language_as_region() -> None:
    """Test that the language itself can be interpreted as a region."""
    assert language.matches(
        "fr",
        ["en-US", "en-GB", "fr-CA", "fr-FR"],
    ) == [
        "fr-FR",
        "fr-CA",
    ]


def test_zh_hant() -> None:
    """Test that the zh-Hant defaults to HK."""
    assert language.matches(
        "zh-Hant",
        ["en-US", "en-GB", "zh-CN", "zh-HK", "zh-TW"],
    ) == [
        "zh-HK",
        "zh-CN",
        "zh-TW",
    ]


def test_zh_hans() -> None:
    """Test that the zh-Hans defaults to TW."""
    assert language.matches(
        "zh-Hans",
        ["en-US", "en-GB", "zh-CN", "zh-HK", "zh-TW"],
    ) == [
        "zh-TW",
        "zh-CN",
        "zh-HK",
    ]


def test_zh_no_code() -> None:
    """Test that the zh defaults to CN."""
    assert language.matches(
        "zh",
        ["en-US", "en-GB", "zh-CN", "zh-HK", "zh-TW"],
    ) == [
        "zh-CN",
        "zh-HK",
        "zh-TW",
    ]


def test_es_419() -> None:
    """Test that the es-419 matches es dialects."""
    assert language.matches(
        "es-419",
        ["en-US", "en-GB", "es-CL", "es-US", "es-ES"],
    ) == [
        "es-ES",
        "es-CL",
        "es-US",
    ]


def test_sr_latn() -> None:
    """Test that the sr_Latn matches sr dialects."""
    assert language.matches(
        "sr-Latn",
        ["en-US", "en-GB", "sr-CS", "sr-RS"],
    ) == [
        "sr-CS",
        "sr-RS",
    ]
