"""The Curve integration.

This integration allows users to define a piecewise curve based on segments
and use it to transform input values from other entities into output values
based on the defined curve.

The entity can be bound to another sensor entity as its source, taking that
sensor's state as input and applying the curve transformation to produce its
own state.

It can also be used in templates to apply the curve transformation to arbitrary
values.
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# Public API re-exports
from .helpers import (
    interpolate_curve as interpolate_curve,
    parse_segments as parse_segments,
)
from .models import CurveSegment as CurveSegment
from .sensor import CurveSensor as CurveSensor
from .types import CurveConfigEntry as CurveConfigEntry

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CurveConfigEntry) -> bool:
    """Set up Curve from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(
    hass: HomeAssistant, entry: CurveConfigEntry
) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: CurveConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
