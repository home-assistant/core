"""Tests for the HA-side typecode-matching / device-model composition.

Ported from the catalog-enrichment section of the old ``test_api.py``
(``test_typecode_prefix_match_*``, ``test_compute_device_model_*``,
``test_enrich_with_catalog_*``). The library's :class:`aioabrp.AbrpVehicle`
no longer carries ``device_model`` / ``device_manufacturer`` columns, so the
old ``_enrich_with_catalog`` (which returned an enriched vehicle copy) is
replaced here by :func:`compose_device_info`, which returns the composed
``(device_model, device_manufacturer)`` pair for the HA ``DeviceInfo`` layer
without mutating the vehicle. The enrichment assertions are reshaped from
``result.device_model`` / ``result.device_manufacturer`` to the returned
:class:`ComposedDeviceInfo`.
"""

from typing import Any

from aioabrp import AbrpVehicle, CatalogEntry
import pytest

from homeassistant.components.abetterrouteplanner.device_info import (
    ComposedDeviceInfo,
    _compute_device_model,
    _match_catalog_entry,
    _typecode_prefix_match,
    compose_device_info,
)

MOCK_VEHICLE_ID = 12345
MOCK_VEHICLE_NAME = "My Rivian"
MOCK_VEHICLE_MODEL = "rivian:r1t-quad:22:135"
MOCK_PAINT = "Forest Green"


def _build_raw_vehicle(**overrides: Any) -> AbrpVehicle:
    """Build an :class:`aioabrp.AbrpVehicle` from the four identity fields.

    The library's ``AbrpVehicle`` carries only identity fields
    (``vehicle_id`` / ``name`` / ``vehicle_model`` / ``paint``) — no
    composed catalog columns. This builder constructs the minimal vehicle.
    """
    base: dict[str, Any] = {
        "vehicle_id": MOCK_VEHICLE_ID,
        "name": MOCK_VEHICLE_NAME,
        "vehicle_model": MOCK_VEHICLE_MODEL,
        "paint": MOCK_PAINT,
    }
    base.update(overrides)
    return AbrpVehicle(**base)


def _make_entry(
    typecode: str = "rivian:r1s:25:c3-53g:dual",
    *,
    manufacturer: str | None = "Rivian",
    model: str | None = "R1S",
    title: str | None = "Dual Motor",
    start_year: int | None = 2025,
    end_year: int | None = None,
    battery_capacity_wh: int | None = None,
) -> CatalogEntry:
    """Build a :class:`aioabrp.CatalogEntry` for the prefix-match tests.

    The factory exists for readability in the parametrize bodies below.
    """
    return CatalogEntry(
        typecode=typecode,
        manufacturer=manufacturer,
        model=model,
        title=title,
        start_year=start_year,
        end_year=end_year,
        battery_capacity_wh=battery_capacity_wh,
    )


# ---------------------------------------------------------------------------
# _compute_device_model
# ---------------------------------------------------------------------------
#
# The catalog's display metadata is composed once into the device-card
# ``DeviceInfo.model`` display string. The composition is
# longest-typecode-prefix-match (not exact ``dict.get``) so a vehicle whose
# typecode is a suffix-decorated variant of a catalog ancestor still
# resolves. Each parametrize case below pins one cell of the year-x-title
# state machine plus the longest-prefix-wins and corrupted-catalog cases.


@pytest.mark.parametrize(
    ("typecode", "catalog", "expected"),
    [
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {},
            None,
            id="empty_catalog_returns_none",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {"audi:q4:45:24:77:meb:sb:awd": _make_entry("audi:q4:45:24:77:meb:sb:awd")},
            None,
            id="no_prefix_match_returns_none",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    manufacturer="Rivian",
                    model="R1S",
                    title="Dual Motor",
                    start_year=2024,
                    end_year=2025,
                ),
            },
            "Rivian R1S 2024-2025 Dual Motor",
            id="both_years_present_yields_range_segment",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    start_year=2025,
                    end_year=None,
                ),
            },
            "Rivian R1S 2025 Dual Motor",
            id="start_year_only_yields_bare_year_segment",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    start_year=None,
                    end_year=2023,
                ),
            },
            "Rivian R1S Dual Motor",
            id="end_year_only_drops_year_segment_entirely",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    start_year=None,
                    end_year=None,
                ),
            },
            "Rivian R1S Dual Motor",
            id="both_years_missing_drops_year_segment",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    title=None,
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025",
            id="title_absent_yields_no_title_segment",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    title="   ",
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025",
            id="title_whitespace_only_dropped_via_strip_guard",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual:perf",
            {
                "rivian": _make_entry(
                    "rivian",
                    manufacturer="Rivian",
                    model="(generic)",
                    title=None,
                    start_year=None,
                ),
                "rivian:r1s:25": _make_entry(
                    "rivian:r1s:25",
                    manufacturer="Rivian",
                    model="R1S",
                    title="2025 lineup",
                    start_year=2025,
                ),
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    manufacturer="Rivian",
                    model="R1S",
                    title="Dual Motor",
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025 Dual Motor",
            id="longest_prefix_wins_across_three_ancestors",
        ),
        pytest.param(
            "rivian:r1s:25:c3-53g:dual:perf",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    manufacturer=None,
                    model="R1S",
                    title="Dual Motor",
                    start_year=2025,
                ),
                "rivian:r1s:25": _make_entry(
                    "rivian:r1s:25",
                    manufacturer="Rivian",
                    model="R1S",
                    title="2025 lineup",
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025 2025 lineup",
            id="longest_prefix_with_null_manufacturer_falls_back_to_shorter",
        ),
        # The catalog's only entry is a strict byte-prefix of the target
        # typecode but is NOT a token ancestor on the ``:`` delimiter
        # (``rivian:r1`` vs ``rivian:r1s:25:foo``). Byte-prefix match would
        # falsely pick ``rivian:r1`` and emit a misleading display;
        # token-prefix correctly rejects so the model stays ``None``.
        pytest.param(
            "rivian:r1s:25:foo",
            {
                "rivian:r1": _make_entry(
                    "rivian:r1",
                    manufacturer="Rivian",
                    model="R1",
                    title="(generic)",
                    start_year=2022,
                ),
            },
            None,
            id="token_boundary_rejects_byte_prefix_non_ancestor",
        ),
        # Whitespace-padded ``title`` from the catalog wire must not leak
        # padding into the composed display string; the use-site
        # ``strip()`` guard keeps the helper robust against a directly
        # constructed ``CatalogEntry`` carrying padded text.
        pytest.param(
            "rivian:r1s:25:c3-53g:dual",
            {
                "rivian:r1s:25:c3-53g:dual": _make_entry(
                    "rivian:r1s:25:c3-53g:dual",
                    manufacturer="Rivian",
                    model="R1S",
                    title="  Dual Motor  ",
                    start_year=2025,
                ),
            },
            "Rivian R1S 2025 Dual Motor",
            id="whitespace_padded_title_stripped_in_display",
        ),
    ],
)
def test_compute_device_model_parametrized(
    typecode: str,
    catalog: dict[str, CatalogEntry],
    expected: str | None,
) -> None:
    """Pin :func:`_compute_device_model` across the year-x-title state machine.

    Each case exercises one cell of the composition formula plus the
    longest-prefix selection logic.
    """
    assert _compute_device_model(typecode, catalog) == expected


# ---- _typecode_prefix_match (refinement) ----------------------------------
#
# Standalone unit pin for the token-aware prefix-match predicate. The parent
# ``_compute_device_model`` parametrize above carries one integration-level
# row covering the token-boundary guard
# (``token_boundary_rejects_byte_prefix_non_ancestor``); this sibling
# parametrize exercises the predicate in isolation so a regression that
# flipped the comparison to plain ``str.startswith`` surfaces with a precise
# failure message rather than as a downstream composed-string mismatch.


@pytest.mark.parametrize(
    ("candidate", "target", "expected"),
    [
        pytest.param("rivian:r1s", "rivian:r1s", True, id="exact_equality"),
        pytest.param(
            "rivian:r1s",
            "rivian:r1s:25:foo",
            True,
            id="strict_token_ancestor",
        ),
        pytest.param(
            "rivian:r1",
            "rivian:r1s:25:foo",
            False,
            id="byte_prefix_but_not_token_ancestor",
        ),
        pytest.param(
            "rivian:r1s",
            "tesla:model3:2024",
            False,
            id="disjoint",
        ),
        pytest.param(
            "rivian:r1s:25:foo",
            "rivian:r1s",
            False,
            id="candidate_longer_than_target",
        ),
    ],
)
def test_typecode_prefix_match_parametrized(
    candidate: str,
    target: str,
    expected: bool,
) -> None:
    """Pin :func:`_typecode_prefix_match` token-aware comparison invariants.

    Five cases cover the predicate's correctness floor:

    * **exact_equality** — identical typecodes match (the degenerate case
      where the catalog entry is the target verbatim).
    * **strict_token_ancestor** — ``candidate`` is a strict token-level
      ancestor of ``target``; the next character after ``candidate`` in
      ``target`` must be ``:``.
    * **byte_prefix_but_not_token_ancestor** — the load-bearing negative:
      ``rivian:r1`` is a byte-prefix of ``rivian:r1s:25:foo`` but is NOT a
      token ancestor. A naive ``target.startswith(candidate)`` returns True
      here; the helper must reject.
    * **disjoint** — no shared prefix at all.
    * **candidate_longer_than_target** — ``candidate`` cannot prefix a
      shorter ``target``; the predicate must be asymmetric.
    """
    assert _typecode_prefix_match(candidate, target) is expected


# ---- _match_catalog_entry -------------------------------------------------


def test_match_catalog_entry_picks_longest_usable_ancestor() -> None:
    """Longest-token-ancestor entry with non-None make+model wins."""
    catalog = {
        "rivian:r1s:25": _make_entry(
            "rivian:r1s:25", manufacturer="Rivian", model="R1S"
        ),
        "rivian:r1s:25:c3-53g:dual": _make_entry(
            "rivian:r1s:25:c3-53g:dual", manufacturer="Rivian", model="R1S"
        ),
    }

    best = _match_catalog_entry("rivian:r1s:25:c3-53g:dual:perf", catalog)

    assert best is not None
    assert best.typecode == "rivian:r1s:25:c3-53g:dual"


def test_match_catalog_entry_no_candidate_returns_none() -> None:
    """No token-ancestor with a usable make+model → ``None``."""
    assert _match_catalog_entry("rivian:r1s:25", {}) is None


# ---- compose_device_info (replaces the old _enrich_with_catalog join) -----


def test_compose_device_info_hit_populates_device_model() -> None:
    """Catalog hit → ``device_model`` carries the composed display string.

    Reshaped from the old ``test_enrich_with_catalog_hit_populates_device_model``:
    the library's ``AbrpVehicle`` no longer carries catalog columns, so the
    composed model is asserted on the returned :class:`ComposedDeviceInfo`
    rather than on an enriched vehicle copy.
    """
    raw = _build_raw_vehicle(vehicle_model="rivian:r1s:25:c3-53g:dual:perf")
    catalog = {
        "rivian:r1s:25:c3-53g:dual": _make_entry(
            "rivian:r1s:25:c3-53g:dual",
            manufacturer="Rivian",
            model="R1S",
            title="Dual Motor",
            start_year=2025,
        ),
    }

    result = compose_device_info(raw, catalog)

    assert result == ComposedDeviceInfo(
        device_model="Rivian R1S 2025 Dual Motor",
        device_manufacturer="Rivian",
    )


def test_compose_device_info_miss_device_model_is_none() -> None:
    """Catalog miss → ``device_model`` stays ``None``.

    Skip-on-miss invariant: no typecode-string parsing fallback. Reshaped
    from ``test_enrich_with_catalog_miss_device_model_is_none``.
    """
    raw = _build_raw_vehicle(vehicle_model="rivian:r2:26:ncma91:rwd:w21")

    result = compose_device_info(raw, {})

    assert result.device_model is None


def test_compose_device_info_hit_populates_device_manufacturer() -> None:
    """Catalog hit → ``device_manufacturer`` carries the catalog's make.

    Sibling of ``test_compose_device_info_hit_populates_device_model``: the
    same prefix-matched ``CatalogEntry`` populates both columns of the
    returned :class:`ComposedDeviceInfo`.
    """
    raw = _build_raw_vehicle(vehicle_model="rivian:r1s:25:c3-53g:dual:perf")
    catalog = {
        "rivian:r1s:25:c3-53g:dual": _make_entry(
            "rivian:r1s:25:c3-53g:dual",
            manufacturer="Rivian",
            model="R1S",
            title="Dual Motor",
            start_year=2025,
        ),
    }

    result = compose_device_info(raw, catalog)

    assert result.device_manufacturer == "Rivian"


def test_compose_device_info_miss_device_manufacturer_is_none() -> None:
    """Catalog miss → ``device_manufacturer`` stays ``None``.

    Mirrors the skip-on-miss invariant; reshaped from
    ``test_enrich_with_catalog_miss_device_manufacturer_is_none``.
    """
    raw = _build_raw_vehicle(vehicle_model="rivian:r2:26:ncma91:rwd:w21")

    result = compose_device_info(raw, {})

    assert result.device_manufacturer is None
