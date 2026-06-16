"""Tests for HA-side device-card composition from the display endpoint.

The library's :class:`aioabrp.AbrpVehicle` carries no composed columns; the
device-card strings are composed from the per-typecode
:class:`aioabrp.VehicleModelDisplay` resolved server-side. The server now does
the typecode resolution the integration used to do locally, so these tests
cover only the composition formula (year x title state machine) and the
present/absent branches of :func:`compose_device_info`.
"""

from aioabrp import VehicleModelDisplay
import pytest

from homeassistant.components.abetterrouteplanner.device_info import (
    ComposedDeviceInfo,
    _compose_device_model,
    compose_device_info,
)


def _make_display(
    *,
    manufacturer: str = "Rivian",
    model: str = "R1S",
    years: str = "2025",
    title: str = "Dual Motor",
    start_year: int | None = 2025,
    end_year: int | None = None,
) -> VehicleModelDisplay:
    """Build a VehicleModelDisplay for the composition tests."""
    return VehicleModelDisplay(
        manufacturer=manufacturer,
        model=model,
        years=years,
        title=title,
        start_year=start_year,
        end_year=end_year,
    )


# ---------------------------------------------------------------------------
# _compose_device_model — year x title state machine
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        pytest.param(
            _make_display(start_year=2024, end_year=2025),
            "Rivian R1S 2024-2025 Dual Motor",
            id="both_years_present_yields_range_segment",
        ),
        pytest.param(
            _make_display(start_year=2025, end_year=None),
            "Rivian R1S 2025 Dual Motor",
            id="start_year_only_yields_bare_year_segment",
        ),
        pytest.param(
            _make_display(start_year=None, end_year=2023),
            "Rivian R1S Dual Motor",
            id="end_year_only_drops_year_segment_entirely",
        ),
        pytest.param(
            _make_display(start_year=None, end_year=None),
            "Rivian R1S Dual Motor",
            id="both_years_missing_drops_year_segment",
        ),
        pytest.param(
            _make_display(title="", start_year=2025),
            "Rivian R1S 2025",
            id="title_empty_yields_no_title_segment",
        ),
        pytest.param(
            _make_display(title="   ", start_year=2025),
            "Rivian R1S 2025",
            id="title_whitespace_only_dropped_via_strip_guard",
        ),
        pytest.param(
            _make_display(title="  Dual Motor  ", start_year=2025),
            "Rivian R1S 2025 Dual Motor",
            id="whitespace_padded_title_stripped_in_display",
        ),
    ],
)
def test_compose_device_model_parametrized(
    display: VehicleModelDisplay,
    expected: str,
) -> None:
    """Pin :func:`_compose_device_model` across the year-x-title state machine."""
    assert _compose_device_model(display) == expected


# ---------------------------------------------------------------------------
# compose_device_info — present / absent branches
# ---------------------------------------------------------------------------


def test_compose_device_info_present_populates_both_fields() -> None:
    """Display present → composed model + manufacturer on the pair."""
    display = _make_display(
        manufacturer="Rivian",
        model="R1S",
        title="Dual Motor",
        start_year=2025,
        end_year=None,
    )

    result = compose_device_info(display)

    assert result == ComposedDeviceInfo(
        device_model="Rivian R1S 2025 Dual Motor",
        device_manufacturer="Rivian",
    )


def test_compose_device_info_none_yields_empty_pair() -> None:
    """Display absent (fetch failed / unknown typecode) → both fields None."""
    result = compose_device_info(None)

    assert result == ComposedDeviceInfo(
        device_model=None,
        device_manufacturer=None,
    )
