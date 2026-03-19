"""Device functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.exceptions import TemplateError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class DeviceExtension(BaseTemplateExtension):
    """Extension for device-related template functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the device extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "device_entities",
                    self.device_entities,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "device_id",
                    self.device_id,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "device_name",
                    self.device_name,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "device_attr",
                    self.device_attr,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "is_device_attr",
                    self.is_device_attr,
                    as_global=True,
                    as_test=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
            ],
        )

    def device_entities(self, _device_id: str) -> Iterable[str]:
        """Get entity ids for entities tied to a device."""
        entity_reg = er.async_get(self.hass)
        entries = er.async_entries_for_device(entity_reg, _device_id)
        return [entry.entity_id for entry in entries]

    def device_id(self, entity_id_or_device_name: str) -> str | None:
        """Get a device ID from an entity ID or device name."""
        entity_reg = er.async_get(self.hass)
        entity = entity_reg.async_get(entity_id_or_device_name)
        if entity is not None:
            return entity.device_id

        dev_reg = dr.async_get(self.hass)
        return next(
            (
                device_id
                for device_id, device in dev_reg.devices.items()
                if (name := device.name_by_user or device.name)
                and (str(entity_id_or_device_name) == name)
            ),
            None,
        )

    def device_name(self, lookup_value: str) -> str | None:
        """Get the device name from an device id, or entity id."""
        device_reg = dr.async_get(self.hass)
        if device := device_reg.async_get(lookup_value):
            return device.name_by_user or device.name

        ent_reg = er.async_get(self.hass)

        try:
            cv.entity_id(lookup_value)
        except vol.Invalid:
            pass
        else:
            if entity := ent_reg.async_get(lookup_value):
                if entity.device_id and (
                    device := device_reg.async_get(entity.device_id)
                ):
                    return device.name_by_user or device.name

        return None

    def device_attr(self, device_or_entity_id: str, attr_name: str) -> Any:
        """Get the device specific attribute."""
        device_reg = dr.async_get(self.hass)
        if not isinstance(device_or_entity_id, str):
            raise TemplateError("Must provide a device or entity ID")
        device = None
        if (
            "." in device_or_entity_id
            and (_device_id := self.device_id(device_or_entity_id)) is not None
        ):
            device = device_reg.async_get(_device_id)
        elif "." not in device_or_entity_id:
            device = device_reg.async_get(device_or_entity_id)
        if device is None or not hasattr(device, attr_name):
            return None
        return getattr(device, attr_name)

    def is_device_attr(
        self, device_or_entity_id: str, attr_name: str, attr_value: Any
    ) -> bool:
        """Test if a device's attribute is a specific value."""
        return bool(self.device_attr(device_or_entity_id, attr_name) == attr_value)
