"""Helper methods for language selection in Home Assistant."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math
import operator
import re

from homeassistant.const import MATCH_ALL

SEPARATOR_RE = re.compile(r"[-_]")
SAME_LANGUAGES = (
    # no = spoken Norwegian
    # nb = written Norwegian (Bokmål)
    ("nb", "no"),
    # he = Hebrew new code
    # iw = Hebrew old code
    ("he", "iw"),
)


def preferred_regions(
    language: str,
    country: str | None = None,
    code: str | None = None,
) -> Iterable[str]:
    """Yield an ordered list of regions for a language based on country/code hints.

    Regions should be checked for support in the returned order if no other
    information is available.
    """
    if country is not None:
        yield country.upper()

    if language == "en":
        # Prefer U.S. English if no country
        if country is None:
            yield "US"
    elif language == "zh":
        if code == "Hant":
            yield "HK"
            yield "TW"
        else:
            yield "CN"

    # fr -> fr-FR
    yield language.upper()


def is_region(language: str, region: str | None) -> bool:
    """Return true if region is not known to be a script/code instead."""
    if language == "es":
        return region != "419"

    if language == "sr":
        return region != "Latn"

    if language == "zh":
        return region not in ("Hans", "Hant")

    return True


def is_language_match(lang_1: str, lang_2: str) -> bool:
    """Return true if two languages are considered the same."""
    if lang_1 == lang_2:
        # Exact match
        return True

    if tuple(sorted([lang_1, lang_2])) in SAME_LANGUAGES:
        return True

    return False


@dataclass
class Dialect:
    """Language with optional region and script/code."""

    language: str
    region: str | None
    code: str | None = None

    def __post_init__(self) -> None:
        """Fix casing of language/region."""
        # Languages are lower-cased
        self.language = self.language.casefold()

        if self.region is not None:
            # Regions are upper-cased
            self.region = self.region.upper()

    def score(
        self, dialect: Dialect, country: str | None = None
    ) -> tuple[float, float]:
        """Return score for match with another dialect where higher is better.

        Score < 0 indicates a failure to match.
        """
        if not is_language_match(self.language, dialect.language):
            # Not a match
            return (-1, 0)

        is_exact_language = self.language == dialect.language

        if (self.region is None) and (dialect.region is None):
            # Weak match with no region constraint
            # Prefer exact language match
            return (2 if is_exact_language else 1, 0)

        if (self.region is not None) and (dialect.region is not None):
            if self.region == dialect.region:
                # Same language + region match
                # Prefer exact language match
                return (
                    math.inf,
                    1 if is_exact_language else 0,
                )

            # Regions are both set, but don't match
            return (0, 0)

        # Generate ordered list of preferred regions
        pref_regions = list(
            preferred_regions(
                self.language,
                country=country,
                code=self.code,
            )
        )

        try:
            # Determine score based on position in the preferred regions list.
            if self.region is not None:
                region_idx = pref_regions.index(self.region)
            elif dialect.region is not None:
                region_idx = pref_regions.index(dialect.region)
            else:
                # Can't happen, but mypy is not smart enough
                raise ValueError

            # More preferred regions are at the front.
            # Add 1 to boost above a weak match where no regions are set.
            return (1 + (len(pref_regions) - region_idx), 0)
        except ValueError:
            # Region was not in preferred list
            pass

        # Not a preferred region
        return (0, 0)

    @staticmethod
    def parse(tag: str) -> Dialect:
        """Parse language tag into language/region/code."""
        parts = SEPARATOR_RE.split(tag, maxsplit=1)
        language = parts[0]
        region: str | None = None
        code: str | None = None

        if len(parts) > 1:
            region_or_code = parts[1]
            if is_region(language, region_or_code):
                # US, GB, etc.
                region = region_or_code
            else:
                # Hant, 419, etc.
                code = region_or_code

        return Dialect(
            language=language,
            region=region,
            code=code,
        )


def matches(
    target: str, supported: Iterable[str], country: str | None = None
) -> list[str]:
    """Return a sorted list of matching language tags based on a target tag and country hint."""
    if target == MATCH_ALL:
        return list(supported)

    target_dialect = Dialect.parse(target)

    # Higher score is better
    scored = sorted(
        (
            (
                dialect := Dialect.parse(tag),
                target_dialect.score(dialect, country=country),
                tag,
            )
            for tag in supported
        ),
        key=operator.itemgetter(1),
        reverse=True,
    )

    # Score < 0 is not a match
    return [tag for _dialect, score, tag in scored if score[0] >= 0]


def intersect(languages_1: set[str], languages_2: set[str]) -> set[str]:
    """Intersect two sets of languages using is_match for aliases."""
    languages = set()
    for lang_1 in languages_1:
        for lang_2 in languages_2:
            if is_language_match(lang_1, lang_2):
                languages.add(lang_1)

    return languages
