"""HA-side device-card composition from the v2 display endpoint.

The :class:`aioabrp.AbrpVehicle` returned by the library carries only the
vehicle identity fields (``vehicle_id`` / ``name`` / ``vehicle_model`` /
``paint``). The device-card display string is composed from the per-typecode
:class:`aioabrp.VehicleModelDisplay` resolved server-side by
:meth:`aioabrp.AbrpClient.async_get_vehicle_model_display`. Composition
deliberately stays in the Home Assistant layer: it is HA-presentation policy,
not API surface.

Rather than mutating the vehicle, :func:`compose_device_info` returns the
composed ``(device_model, device_manufacturer)`` pair as a
:class:`ComposedDeviceInfo` for the setup layer to attach to its
``DeviceInfo``.
"""

from dataclasses import dataclass

from aioabrp import VehicleModelDisplay


@dataclass(frozen=True, slots=True)
class ComposedDeviceInfo:
    """Composed device-card display fields for one vehicle.

    Both fields are ``None`` when no display metadata is available (the
    per-typecode display fetch failed or 404'd for an unknown typecode); the
    device card then falls back to the raw ``vehicle_model`` typecode (Model)
    and the integration name (Manufacturer) at the setup layer.
    """

    device_model: str | None
    device_manufacturer: str | None


def _compose_device_model(display: VehicleModelDisplay) -> str:
    """Build the :attr:`DeviceInfo.model` display string from display metadata.

    Build formula:

        "{manufacturer} {model}" + optional " {startYear-endYear or startYear}"
                                  + optional " {title}"

    The year segment is dropped when ``start_year`` is missing (covers both
    "no start_year" and "end_year-only"). ``VehicleModelDisplay.title`` is the
    trim only (e.g. ``"Long Range"``); it is appended stripped and dropped
    when blank.
    """
    parts = [f"{display.manufacturer} {display.model}"]
    if display.start_year is not None and display.end_year is not None:
        parts.append(f"{display.start_year}-{display.end_year}")
    elif display.start_year is not None:
        parts.append(str(display.start_year))
    if title := display.title.strip():
        parts.append(title)
    return " ".join(parts)


def compose_device_info(
    display: VehicleModelDisplay | None,
) -> ComposedDeviceInfo:
    """Compose device-card fields from one vehicle's display metadata.

    Display present: return a :class:`ComposedDeviceInfo` carrying the
    composed ``device_model`` and the ``device_manufacturer``. Display absent
    (``None`` — the fetch failed or the typecode is unknown to ABRP): both
    stay ``None`` and the device card falls back to the raw ``vehicle_model``
    typecode (Model) and the integration name (Manufacturer) at the setup
    layer.

    No typecode-string parsing fallback. Skip-on-miss beats best-effort
    synthesis — a derived "RIVIAN" from a raw typecode reads worse than the
    raw typecode, and renders correctly once the display fetch next succeeds.
    """
    if display is None:
        return ComposedDeviceInfo(device_model=None, device_manufacturer=None)
    return ComposedDeviceInfo(
        device_model=_compose_device_model(display),
        device_manufacturer=display.manufacturer,
    )
