"""Area functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.template.helpers import resolve_area_id

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class AreaExtension(BaseTemplateExtension):
    """Extension for area-related template functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the area extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "areas",
                    self.areas,
                    as_global=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "area_id",
                    self.area_id,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "area_name",
                    self.area_name,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "area_entities",
                    self.area_entities,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "area_devices",
                    self.area_devices,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
            ],
        )

    def areas(self) -> Iterable[str | None]:
        """Return all areas."""
        return list(ar.async_get(self.hass).areas)

    def area_id(self, lookup_value: str) -> str | None:
        """Get the area ID from an area name, alias, device id, or entity id."""
        return resolve_area_id(self.hass, lookup_value)

    def _get_area_name(self, area_reg: ar.AreaRegistry, valid_area_id: str) -> str:
        """Get area name from valid area ID."""
        area = area_reg.async_get_area(valid_area_id)
        assert area
        return area.name

    def area_name(self, lookup_value: str) -> str | None:
        """Get the area name from an area id, device id, or entity id."""
        area_reg = ar.async_get(self.hass)
        if area := area_reg.async_get_area(lookup_value):
            return area.name

        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)
        # Import here, not at top-level to avoid circular import
        from homeassistant.helpers import config_validation as cv  # noqa: PLC0415

        try:
            cv.entity_id(lookup_value)
        except vol.Invalid:
            pass
        else:
            if entity := ent_reg.async_get(lookup_value):
                # If entity has an area ID, get the area name for that
                if entity.area_id:
                    return self._get_area_name(area_reg, entity.area_id)
                # If entity has a device ID and the device exists with an area ID, get the
                # area name for that
                if (
                    entity.device_id
                    and (device := dev_reg.async_get(entity.device_id))
                    and device.area_id
                ):
                    return self._get_area_name(area_reg, device.area_id)

        if (device := dev_reg.async_get(lookup_value)) and device.area_id:
            return self._get_area_name(area_reg, device.area_id)

        return None

    def area_entities(self, area_id_or_name: str) -> Iterable[str]:
        """Return entities for a given area ID or name."""
        _area_id: str | None
        # if area_name returns a value, we know the input was an ID, otherwise we
        # assume it's a name, and if it's neither, we return early
        if self.area_name(area_id_or_name) is None:
            _area_id = self.area_id(area_id_or_name)
        else:
            _area_id = area_id_or_name
        if _area_id is None:
            return []
        ent_reg = er.async_get(self.hass)
        entity_ids = [
            entry.entity_id for entry in er.async_entries_for_area(ent_reg, _area_id)
        ]
        dev_reg = dr.async_get(self.hass)
        # We also need to add entities tied to a device in the area that don't themselves
        # have an area specified since they inherit the area from the device.
        entity_ids.extend(
            [
                entity.entity_id
                for device in dr.async_entries_for_area(dev_reg, _area_id)
                for entity in er.async_entries_for_device(ent_reg, device.id)
                if entity.area_id is None
            ]
        )
        return entity_ids

    def area_devices(self, area_id_or_name: str) -> Iterable[str]:
        """Return device IDs for a given area ID or name."""
        _area_id: str | None
        # if area_name returns a value, we know the input was an ID, otherwise we
        # assume it's a name, and if it's neither, we return early
        if self.area_name(area_id_or_name) is not None:
            _area_id = area_id_or_name
        else:
            _area_id = self.area_id(area_id_or_name)
        if _area_id is None:
            return []
        dev_reg = dr.async_get(self.hass)
        entries = dr.async_entries_for_area(dev_reg, _area_id)
        return [entry.id for entry in entries]
