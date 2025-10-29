"""Jinja2 extension for curve interpolation functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template.helpers import raise_no_default

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.components.curve import CurveSegment, CurveSensor
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.template import TemplateEnvironment

_SENTINEL = object()


def _get_curve_entity(hass: HomeAssistant | None, curve_ref: str) -> CurveSensor:
    if hass is None:  # pragma: no cover
        raise TemplateError("Home Assistant instance not available")

    from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN  # noqa: PLC0415

    sensor_component = hass.data.get(SENSOR_DOMAIN)
    if not sensor_component:
        raise TemplateError("Sensor component not loaded")

    entity = sensor_component.get_entity(curve_ref)
    if not entity:
        raise TemplateError(f"Curve entity {curve_ref!r} not found")

    from homeassistant.components.curve import CurveSensor  # noqa: PLC0415

    if not isinstance(entity, CurveSensor):
        raise TemplateError(f"{curve_ref!r} is not a curve entity")
    return entity


def _resolve_curve(
    hass: HomeAssistant | None, curve_ref: str | list
) -> list[CurveSegment]:
    from homeassistant.components.curve import parse_segments  # noqa: PLC0415

    if isinstance(curve_ref, str):  # Reference to configured curve by entity ID
        entity = _get_curve_entity(hass, curve_ref)

        return entity.segments

    if isinstance(curve_ref, (tuple, list)):  # Inline segments definition
        return parse_segments(curve_ref)

    raise TemplateError("Second argument must be curve ID (string) or segments (list)")


class CurveExtension(BaseTemplateExtension):
    """Jinja2 extension for curve interpolation."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction("curve", self.curve, as_global=True, as_filter=True),
            ],
        )

    def curve(
        self,
        value: Any,
        curve_ref: str | list[dict[str, Any]] | list[list[float]],
        default: Any = _SENTINEL,
    ) -> Any:
        """Interpolate value on a curve.

        Can be used in two ways:

        * curve(x, entity_id, [default]) - Reference a configured curve by entity_id
        * curve(x, segments, [default]) - Use inline segment definition
        """
        try:
            x = float(value)
        except (ValueError, TypeError):
            if default is _SENTINEL:
                raise_no_default("curve", value)
            return default

        from homeassistant.components.curve import interpolate_curve  # noqa: PLC0415

        try:
            curve_segments = _resolve_curve(self.environment.hass, curve_ref)
        except Exception as err:
            if default is _SENTINEL:
                raise TemplateError(f"Failed to look up curve: {err}") from err
            return default

        # `interpolate_curve` is infallible here, since we're sure we have segments
        return interpolate_curve(x, curve_segments)
