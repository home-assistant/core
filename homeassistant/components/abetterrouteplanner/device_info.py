"""HA-side typecode matching and device-model composition.

The :class:`aioabrp.AbrpVehicle` returned by the library carries only the
vehicle identity fields (``vehicle_id`` / ``name`` / ``vehicle_model`` /
``paint``) — it does not carry composed ``device_model`` /
``device_manufacturer`` columns. Joining a vehicle's typecode against the
v2 catalog to compose the device-card display string deliberately stays in
the Home Assistant layer: it is HA-presentation policy, not API surface.

This module ports that join (longest-token-prefix match + display-string
composition) from the old in-tree ``api.py``. Rather than mutating the
vehicle, :func:`compose_device_info` returns the composed
``(device_model, device_manufacturer)`` pair as a :class:`ComposedDeviceInfo`
for the setup layer to attach to its ``DeviceInfo``.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from aioabrp import AbrpVehicle, CatalogEntry


@dataclass(frozen=True, slots=True)
class ComposedDeviceInfo:
    """Composed device-card display fields for one vehicle.

    Both fields are ``None`` on a catalog miss; the device card then falls
    back to the raw ``vehicle_model`` typecode (Model) and the integration
    name (Manufacturer) at the setup layer.
    """

    device_model: str | None
    device_manufacturer: str | None


def _typecode_prefix_match(candidate: str, target: str) -> bool:
    """True if ``candidate`` is a colon-token ancestor of ``target``.

    Either exact equality, or ``target`` starts with ``candidate + ":"`` —
    so ``rivian:r1s`` matches ``rivian:r1s:25:...`` but ``rivian:r1`` does
    NOT match ``rivian:r1s:...``. Token-boundary discipline matches ABRP's
    hierarchical typecode convention (``manufacturer:model:year:battery:
    drivetrain:...``) so a future short-ancestor catalog row doesn't
    cross-match a longer descendant from an unrelated lineage.
    """
    return candidate == target or target.startswith(candidate + ":")


def _match_catalog_entry(
    typecode: str, catalog: Mapping[str, CatalogEntry]
) -> CatalogEntry | None:
    """Select the longest-prefix catalog entry usable for device-card display.

    Picks the entry whose ``typecode`` is the longest colon-token ancestor
    of ``typecode`` AND whose ``manufacturer`` + ``model`` columns are
    non-None (a malformed longest match must not shadow a usable shorter
    one). Returns ``None`` when nothing matches.

    Equal-length ties are provably impossible: two distinct strings A and B
    of equal length n that both prefix-match target T would both equal T[:n],
    so A == T[:n] == B → A == B, contradicting distinctness. No tie-break
    code path is needed.
    """
    candidates = [
        entry
        for entry in catalog.values()
        if entry.manufacturer
        and entry.model
        and _typecode_prefix_match(entry.typecode, typecode)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: len(entry.typecode))


def _compose_device_model(best: CatalogEntry) -> str:
    """Build the :attr:`DeviceInfo.model` display string from a catalog entry.

    Build formula:

        "{manufacturer} {model}" + optional " {startYear-endYear or startYear}"
                                  + optional " {title}"

    The year segment is dropped when ``start_year`` is missing (covers both
    "no start_year" and "end_year-only"). The title segment is appended
    stripped: under normal wire flow ``_str_or_none`` has already
    normalised the input at parse time, but the use-site ``strip()``
    keeps the helper robust against any directly-constructed
    :class:`CatalogEntry` that happens to carry padded text.
    """
    parts = [f"{best.manufacturer} {best.model}"]
    if best.start_year is not None and best.end_year is not None:
        parts.append(f"{best.start_year}-{best.end_year}")
    elif best.start_year is not None:
        parts.append(str(best.start_year))
    if best.title and (title := best.title.strip()):
        parts.append(title)
    return " ".join(parts)


def _compute_device_model(
    typecode: str, catalog: Mapping[str, CatalogEntry]
) -> str | None:
    """Compose the display string for :attr:`DeviceInfo.model` from the v2 catalog.

    Thin wrapper retained for the parametrized regression test; delegates to
    :func:`_match_catalog_entry` + :func:`_compose_device_model`. Returns
    ``None`` when nothing matches — the caller then falls back to the raw
    typecode at the device-info layer.
    """
    best = _match_catalog_entry(typecode, catalog)
    return _compose_device_model(best) if best is not None else None


def compose_device_info(
    vehicle: AbrpVehicle, catalog: Mapping[str, CatalogEntry]
) -> ComposedDeviceInfo:
    """Join one vehicle with the v2 catalog (skip-on-miss).

    Catalog hit: return a :class:`ComposedDeviceInfo` carrying the composed
    ``device_model`` and the catalog ``device_manufacturer``. Catalog miss:
    both stay ``None`` and the device card falls back to the raw
    ``vehicle_model`` typecode (Model) and the integration name
    (Manufacturer) at the setup layer.

    No typecode-string parsing fallback. Skip-on-miss beats best-effort
    synthesis — a derived "RIVIAN" from a raw typecode reads worse than
    ``unknown``, and renders better once ABRP catalogs the vehicle on the
    next coordinator reload.
    """
    best = _match_catalog_entry(vehicle.vehicle_model, catalog)
    if best is None:
        return ComposedDeviceInfo(device_model=None, device_manufacturer=None)
    return ComposedDeviceInfo(
        device_model=_compose_device_model(best),
        device_manufacturer=best.manufacturer,
    )
