"""Regression tests closing small tail-end coverage gaps.

Covers models.py's unknown-hardwareVersion fallbacks, const.py's JpegSize
helpers' remaining branches, and cloud_ssl.py's cached-instance return paths
that :mod:`tests.components.bosch_shc_camera.test_cloud_ssl` does not
exercise (that file only covers ``async_get_bosch_cloud_ssl_context``, never
``async_get_bosch_cloud_session`` / ``async_bosch_cloud_session_cm``).
"""

import asyncio

import pytest

from homeassistant.components.bosch_shc_camera.cloud_ssl import (
    async_bosch_cloud_session_cm,
    async_get_bosch_cloud_session,
)
from homeassistant.components.bosch_shc_camera.const import (
    JPEG_SIZE_MEDIUM,
    JPEG_SIZE_THUMB,
    jpeg_size_for_width,
    with_jpeg_size,
)
from homeassistant.components.bosch_shc_camera.models import (
    DEFAULT_MODEL,
    get_display_name,
    get_model_config,
)
from homeassistant.core import HomeAssistant

# ── models.py ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("hw_version", "expected_generation"),
    [
        pytest.param("HOME_Eyes_Outdoor", 2, id="known-model"),
        pytest.param("NOT_A_REAL_MODEL", DEFAULT_MODEL.generation, id="unknown-model"),
    ],
)
def test_get_model_config(hw_version: str, expected_generation: int) -> None:
    """Known models return their own config; unknown ones fall back to DEFAULT_MODEL."""
    assert get_model_config(hw_version).generation == expected_generation


@pytest.mark.parametrize(
    ("hw_version", "expected"),
    [
        pytest.param(
            "HOME_Eyes_Outdoor", "Eyes Außenkamera II", id="known-model-display-name"
        ),
        pytest.param(
            "SomeIndoorGadget360",
            "Innenkamera (SomeIndoorGadget360)",
            id="unknown-indoor-fallback",
        ),
        pytest.param(
            "SomeOutdoorEyesGadget",
            "Außenkamera (SomeOutdoorEyesGadget)",
            id="unknown-outdoor-fallback",
        ),
        pytest.param(
            "TotallyUnrecognized",
            "TotallyUnrecognized",
            id="unknown-raw-value-fallback",
        ),
    ],
)
def test_get_display_name(hw_version: str, expected: str) -> None:
    """Unknown hardwareVersion strings hit the dynamic indoor/outdoor/raw fallbacks."""
    assert get_display_name(hw_version) == expected


# ── const.py ──────────────────────────────────────────────────────────────


def test_jpeg_size_for_width_medium_range() -> None:
    """A width strictly between THUMB and MEDIUM maps onto JPEG_SIZE_MEDIUM."""
    width = JPEG_SIZE_THUMB + 1
    assert width <= JPEG_SIZE_MEDIUM
    assert jpeg_size_for_width(width) == JPEG_SIZE_MEDIUM


@pytest.mark.parametrize(
    ("url", "size", "expected"),
    [
        pytest.param(
            "https://cam.example/snap.jpg?JpegSize=1206",
            JPEG_SIZE_THUMB,
            "https://cam.example/snap.jpg?JpegSize=320",
            id="existing-param-replaced",
        ),
        pytest.param(
            "https://cam.example/snap.jpg?foo=bar",
            JPEG_SIZE_THUMB,
            "https://cam.example/snap.jpg?foo=bar&JpegSize=320",
            id="no-param-appended-with-ampersand",
        ),
        pytest.param(
            "https://cam.example/snap.jpg",
            JPEG_SIZE_THUMB,
            "https://cam.example/snap.jpg?JpegSize=320",
            id="no-param-appended-with-question-mark",
        ),
    ],
)
def test_with_jpeg_size(url: str, size: int, expected: str) -> None:
    """Existing ``JpegSize=`` params are replaced; missing ones are appended."""
    assert with_jpeg_size(url, size) == expected


# ── cloud_ssl.py ──────────────────────────────────────────────────────────


async def test_get_bosch_cloud_session_returns_cached_instance(
    hass: HomeAssistant,
) -> None:
    """A second call returns the exact same, still-open session (no rebuild)."""
    first = await async_get_bosch_cloud_session(hass)
    second = await async_get_bosch_cloud_session(hass)
    assert first is second
    assert not first.closed


async def test_get_bosch_cloud_session_concurrent_callers_build_only_once(
    hass: HomeAssistant,
) -> None:
    """Concurrent first-callers race the lock but only build one session."""
    results = await asyncio.gather(
        *[async_get_bosch_cloud_session(hass) for _ in range(5)]
    )
    assert len({id(r) for r in results}) == 1


async def test_bosch_cloud_session_cm_yields_the_shared_session(
    hass: HomeAssistant,
) -> None:
    """The context manager yields the same shared session and never closes it."""
    shared = await async_get_bosch_cloud_session(hass)
    async with async_bosch_cloud_session_cm(hass) as session:
        assert session is shared
    assert not shared.closed
