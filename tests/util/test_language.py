"""Test Home Assistant language util methods."""

import pytest

from homeassistant.const import MATCH_ALL
from homeassistant.util import language


def test_match_all() -> None:
    """Test MATCH_ALL."""
    assert language.matches(MATCH_ALL, ["fr-Fr", "en-US", "en-GB"]) == [
        "fr-Fr",
        "en-US",
        "en-GB",
    ]


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


def test_country_preferred_over_family() -> None:
    """Test that country hint is preferred over language family."""
    assert (
        language.matches(
            "de",
            ["de", "de-CH", "de-DE"],
            country="CH",
        )[0]
        == "de-CH"
    )
    assert (
        language.matches(
            "de",
            ["de", "de-CH", "de-DE"],
            country="DE",
        )[0]
        == "de-DE"
    )


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
    """Test that the zh-Hant matches HK or TW."""
    assert language.matches(
        "zh-Hant",
        ["en-US", "en-GB", "zh-CN", "zh-HK"],
    ) == [
        "zh-HK",
        "zh-CN",
    ]

    assert language.matches(
        "zh-Hant",
        ["en-US", "en-GB", "zh-CN", "zh-TW"],
    ) == [
        "zh-TW",
        "zh-CN",
    ]


@pytest.mark.parametrize("target", ["zh-Hant", "zh-Hans"])
def test_zh_with_country(target: str) -> None:
    """Test that the zh-Hant/zh-Hans still matches country when provided."""
    supported = ["en-US", "en-GB", "zh-CN", "zh-HK", "zh-TW"]
    assert (
        language.matches(
            target,
            supported,
            country="TW",
        )[0]
        == "zh-TW"
    )
    assert (
        language.matches(
            target,
            supported,
            country="HK",
        )[0]
        == "zh-HK"
    )
    assert (
        language.matches(
            target,
            supported,
            country="CN",
        )[0]
        == "zh-CN"
    )


def test_zh_hans() -> None:
    """Test that the zh-Hans matches CN first."""
    assert language.matches(
        "zh-Hans",
        ["en-US", "en-GB", "zh-CN", "zh-HK", "zh-TW"],
    ) == [
        "zh-CN",
        "zh-HK",
        "zh-TW",
    ]


def test_zh_no_code() -> None:
    """Test that the zh defaults to CN first."""
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

    # Prefer exact match with code
    assert language.matches("sr", ["sr-Latn", "sr"]) == ["sr", "sr-Latn"]


@pytest.mark.parametrize(
    ("target", "supported", "expected"),
    [
        pytest.param(
            "zh-hant", ["zh-Hans", "zh-Hant"], ["zh-Hant", "zh-Hans"], id="zh-hant"
        ),
        pytest.param(
            "ZH-HANS", ["zh-Hant", "zh-Hans"], ["zh-Hans", "zh-Hant"], id="ZH-HANS"
        ),
        pytest.param("zh_hant", ["zh-CN", "zh-TW"], ["zh-TW", "zh-CN"], id="zh_hant"),
        pytest.param("SR-latn", ["sr", "sr-Latn"], ["sr-Latn", "sr"], id="SR-latn"),
    ],
)
def test_script_case_insensitive(
    target: str, supported: list[str], expected: list[str]
) -> None:
    """Test that script subtags are matched case-insensitively."""
    assert language.matches(target, supported) == expected


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        pytest.param(
            "zh-Hant-TW", language.Dialect("zh", "TW", "Hant"), id="zh-Hant-TW"
        ),
        pytest.param(
            "zh_Hans_CN", language.Dialect("zh", "CN", "Hans"), id="zh_Hans_CN"
        ),
        pytest.param(
            "sr-Latn-RS", language.Dialect("sr", "RS", "Latn"), id="sr-Latn-RS"
        ),
    ],
)
def test_parse_script_and_region(tag: str, expected: language.Dialect) -> None:
    """Test parsing a tag with both a script and a region."""
    assert language.Dialect.parse(tag) == expected


@pytest.mark.parametrize(
    ("target", "supported", "country", "expected"),
    [
        pytest.param(
            "zh-TW",
            ["zh-Hans-CN", "zh-Hant-TW"],
            None,
            ["zh-Hant-TW", "zh-Hans-CN"],
            id="zh-TW",
        ),
        pytest.param(
            "sr", ["sr-Latn-RS", "sr-RS"], "RS", ["sr-RS", "sr-Latn-RS"], id="sr"
        ),
        pytest.param(
            "sr-Latn",
            ["sr-RS", "sr-Latn-RS"],
            "RS",
            ["sr-Latn-RS", "sr-RS"],
            id="sr-Latn",
        ),
    ],
)
def test_script_and_region_match(
    target: str, supported: list[str], country: str | None, expected: list[str]
) -> None:
    """Test matching language-script-region tags."""
    assert language.matches(target, supported, country=country) == expected


def test_no_nb_same() -> None:
    """Test that the no/nb are interchangeable."""
    assert language.matches(
        "no",
        ["en-US", "en-GB", "nb"],
    ) == ["nb"]
    assert language.matches(
        "nb",
        ["en-US", "en-GB", "no"],
    ) == ["no"]


def test_no_nb_prefer_exact() -> None:
    """Test exact language preferred over interchangeable language."""
    assert language.matches(
        "no",
        ["en-US", "en-GB", "nb", "no"],
    ) == ["no", "nb"]
    assert language.matches(
        "no",
        ["en-US", "en-GB", "no", "nb"],
    ) == ["no", "nb"]


def test_no_nb_prefer_exact_regions() -> None:
    """Test that the exact language/region is preferred."""
    assert language.matches(
        "no-AA",
        ["en-US", "en-GB", "nb-AA", "no-AA"],
    ) == ["no-AA", "nb-AA"]
    assert language.matches(
        "no-AA",
        ["en-US", "en-GB", "no-AA", "nb-AA"],
    ) == ["no-AA", "nb-AA"]


def test_he_iw_same() -> None:
    """Test that the he/iw are interchangeable."""
    assert language.matches(
        "he",
        ["en-US", "en-GB", "iw"],
    ) == ["iw"]
    assert language.matches(
        "iw",
        ["en-US", "en-GB", "he"],
    ) == ["he"]


def test_he_iw_prefer_exact() -> None:
    """Test exact language preferred over interchangeable language."""
    assert language.matches(
        "he",
        ["en-US", "en-GB", "iw", "he"],
    ) == ["he", "iw"]
    assert language.matches(
        "he",
        ["en-US", "en-GB", "he", "iw"],
    ) == ["he", "iw"]


def test_he_iw_prefer_exact_regions() -> None:
    """Test that the exact language/region is preferred."""
    assert language.matches(
        "he-IL",
        ["en-US", "en-GB", "iw-IL", "he-IL"],
    ) == ["he-IL", "iw-IL"]
    assert language.matches(
        "he-IL",
        ["en-US", "en-GB", "he-IL", "iw-IL"],
    ) == ["he-IL", "iw-IL"]
