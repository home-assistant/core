"""Index band tables and scoring for the Indoor Air Quality integration.

Adding a new rating standard is purely additive: define its per-source band
tuple, its level cut-offs and its top level, and register it in ``BANDS``,
``LEVEL_BANDS`` and ``LEVEL_TOP``.
"""

from typing import Final, NamedTuple

from .const import (
    CONF_CO,
    CONF_CO2,
    CONF_HCHO,
    CONF_HUMIDITY,
    CONF_NO2,
    CONF_PM,
    CONF_RADON,
    CONF_TEMPERATURE,
    CONF_TVOC,
    CONF_VOC_INDEX,
    LEVEL_EXCELLENT,
    LEVEL_FAIR,
    LEVEL_GOOD,
    LEVEL_INADEQUATE,
    LEVEL_POOR,
    STANDARD_UK,
)


class ScoreBand(NamedTuple):
    """Range -> score mapping used by the index calculator.

    A value matches a band when it satisfies both the optional lower and
    upper bound. ``low_strict`` / ``high_strict`` switch the corresponding
    bound between ``<=`` (default) and ``<``.
    """

    score: int
    low: float | None = None
    high: float | None = None
    low_strict: bool = False
    high_strict: bool = False


def score_from_bands(value: float, bands: tuple[ScoreBand, ...]) -> int:
    """Return the score for the first matching band, defaulting to 1."""
    for band in bands:
        if band.low is not None:
            if band.low_strict:
                if not band.low < value:
                    continue
            elif not band.low <= value:
                continue
        if band.high is not None:
            if band.high_strict:
                if not value < band.high:
                    continue
            elif not value <= band.high:
                continue
        return band.score
    return 1


_BANDS_UK: Final[dict[str, tuple[ScoreBand, ...]]] = {
    CONF_TEMPERATURE: (
        ScoreBand(5, low=18, high=21),
        ScoreBand(4, low=16, high=23, low_strict=True, high_strict=True),
        ScoreBand(3, low=15, high=24, low_strict=True, high_strict=True),
        ScoreBand(2, low=14, high=25, low_strict=True, high_strict=True),
    ),
    CONF_HUMIDITY: (
        ScoreBand(5, low=40, high=60),
        ScoreBand(4, low=30, high=70),
        ScoreBand(3, low=20, high=80),
        ScoreBand(2, low=10, high=90),
    ),
    CONF_CO2: (
        ScoreBand(5, high=600, high_strict=True),
        ScoreBand(4, high=800),
        ScoreBand(3, high=1500),
        ScoreBand(2, high=1800),
    ),
    CONF_TVOC: (
        ScoreBand(5, high=0.1, high_strict=True),
        ScoreBand(4, high=0.3),
        ScoreBand(3, high=0.5),
        ScoreBand(2, high=1.0),
    ),
    CONF_VOC_INDEX: (
        ScoreBand(5, high=50),
        ScoreBand(4, high=115),
        ScoreBand(3, high=180),
        ScoreBand(2, high=260),
    ),
    CONF_PM: (
        ScoreBand(5, high=23),
        ScoreBand(4, high=41),
        ScoreBand(3, high=53),
        ScoreBand(2, high=64),
    ),
    CONF_NO2: (
        ScoreBand(5, high=200, high_strict=True),
        ScoreBand(3, high=400),
    ),
    CONF_CO: (
        ScoreBand(5, low=0, high=0),
        ScoreBand(3, high=7),
    ),
    CONF_HCHO: (
        ScoreBand(5, high=20, high_strict=True),
        ScoreBand(4, high=50),
        ScoreBand(3, high=100),
        ScoreBand(2, high=200),
    ),
    CONF_RADON: (
        ScoreBand(5, low=0, high=0),
        ScoreBand(3, high=20, high_strict=True),
        ScoreBand(2, high=100),
    ),
}

# IAQ score (5 per source, normalized to 0-65) -> human level.
_LEVEL_BANDS_UK: Final[tuple[tuple[int, str], ...]] = (
    (25, LEVEL_INADEQUATE),
    (38, LEVEL_POOR),
    (51, LEVEL_FAIR),
    (60, LEVEL_GOOD),
)

BANDS: Final[dict[str, dict[str, tuple[ScoreBand, ...]]]] = {
    STANDARD_UK: _BANDS_UK,
}

LEVEL_BANDS: Final[dict[str, tuple[tuple[int, str], ...]]] = {
    STANDARD_UK: _LEVEL_BANDS_UK,
}

LEVEL_TOP: Final[dict[str, str]] = {
    STANDARD_UK: LEVEL_EXCELLENT,
}


def level_for_index(standard: str, iaq_index: int) -> str:
    """Return the human readable level for an IAQ index value."""
    for upper, level in LEVEL_BANDS[standard]:
        if iaq_index <= upper:
            return level
    return LEVEL_TOP[standard]
