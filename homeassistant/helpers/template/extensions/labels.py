"""Label functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class LabelExtension(BaseTemplateExtension):
    """Extension for label-related template functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the label extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "labels",
                    self.labels,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "label_id",
                    self.label_id,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "label_name",
                    self.label_name,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "label_description",
                    self.label_description,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "label_areas",
                    self.label_areas,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "label_devices",
                    self.label_devices,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "label_entities",
                    self.label_entities,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
            ],
        )

    def labels(self, lookup_value: Any = None) -> Iterable[str | None]:
        """Return all labels, or those from a area ID, device ID, or entity ID."""
        label_reg = lr.async_get(self.hass)
        if lookup_value is None:
            return list(label_reg.labels)

        ent_reg = er.async_get(self.hass)

        # Import here, not at top-level to avoid circular import
        from homeassistant.helpers import config_validation as cv  # noqa: PLC0415

        lookup_value = str(lookup_value)

        try:
            cv.entity_id(lookup_value)
        except vol.Invalid:
            pass
        else:
            if entity := ent_reg.async_get(lookup_value):
                return list(entity.labels)

        # Check if this could be a device ID
        dev_reg = dr.async_get(self.hass)
        if device := dev_reg.async_get(lookup_value):
            return list(device.labels)

        # Check if this could be a area ID
        area_reg = ar.async_get(self.hass)
        if area := area_reg.async_get_area(lookup_value):
            return list(area.labels)

        return []

    def label_id(self, lookup_value: Any) -> str | None:
        """Get the label ID from a label name."""
        label_reg = lr.async_get(self.hass)
        if label := label_reg.async_get_label_by_name(str(lookup_value)):
            return label.label_id
        return None

    def label_name(self, lookup_value: str) -> str | None:
        """Get the label name from a label ID."""
        label_reg = lr.async_get(self.hass)
        if label := label_reg.async_get_label(lookup_value):
            return label.name
        return None

    def label_description(self, lookup_value: str) -> str | None:
        """Get the label description from a label ID."""
        label_reg = lr.async_get(self.hass)
        if label := label_reg.async_get_label(lookup_value):
            return label.description
        return None

    def _label_id_or_name(self, label_id_or_name: str) -> str | None:
        """Get the label ID from a label name or ID."""
        # If label_name returns a value, we know the input was an ID, otherwise we
        # assume it's a name, and if it's neither, we return early.
        if self.label_name(label_id_or_name) is not None:
            return label_id_or_name
        return self.label_id(label_id_or_name)

    def label_areas(self, label_id_or_name: str) -> Iterable[str]:
        """Return areas for a given label ID or name."""
        if (_label_id := self._label_id_or_name(label_id_or_name)) is None:
            return []
        area_reg = ar.async_get(self.hass)
        entries = ar.async_entries_for_label(area_reg, _label_id)
        return [entry.id for entry in entries]

    def label_devices(self, label_id_or_name: str) -> Iterable[str]:
        """Return device IDs for a given label ID or name."""
        if (_label_id := self._label_id_or_name(label_id_or_name)) is None:
            return []
        dev_reg = dr.async_get(self.hass)
        entries = dr.async_entries_for_label(dev_reg, _label_id)
        return [entry.id for entry in entries]

    def label_entities(self, label_id_or_name: str) -> Iterable[str]:
        """Return entities for a given label ID or name."""
        if (_label_id := self._label_id_or_name(label_id_or_name)) is None:
            return []
        ent_reg = er.async_get(self.hass)
        entries = er.async_entries_for_label(ent_reg, _label_id)
        return [entry.entity_id for entry in entries]
