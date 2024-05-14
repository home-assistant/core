"""Base entity for the Binary sensor as X integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from homeassistant.components.homeassistant import exposed_entities
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, get_device_class
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN as BINARY_SENSOR_AS_X_DOMAIN


class BaseEntity(Entity):
    """Represents a Binary sensor as an X."""

    _attr_should_poll = False
    _is_new_entity: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_title: str,
        domain: str,
        binary_sensor_entity_id: str,
        unique_id: str,
    ) -> None:
        """Initialize Binary sensor as an X."""
        registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        wrapped_binary_sensor = registry.async_get(binary_sensor_entity_id)
        device_id = wrapped_binary_sensor.device_id if wrapped_binary_sensor else None
        entity_category = (
            wrapped_binary_sensor.entity_category if wrapped_binary_sensor else None
        )
        has_entity_name = (
            wrapped_binary_sensor.has_entity_name if wrapped_binary_sensor else False
        )

        name: str | None = config_entry_title
        if wrapped_binary_sensor:
            name = wrapped_binary_sensor.original_name

        self._device_id = device_id
        if device_id and (device := device_registry.async_get(device_id)):
            self._attr_device_info = DeviceInfo(
                connections=device.connections,
                identifiers=device.identifiers,
            )
        self._attr_entity_category = entity_category
        self._attr_has_entity_name = has_entity_name
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._binary_sensor_entity_id = binary_sensor_entity_id

        self._is_new_entity = (
            registry.async_get_entity_id(domain, BINARY_SENSOR_AS_X_DOMAIN, unique_id)
            is None
        )

    @callback
    def async_state_changed_listener(
        self, event: Event[EventStateChangedData] | None = None
    ) -> None:
        """Handle child updates."""
        if (
            state := self.hass.states.get(self._binary_sensor_entity_id)
        ) is None or state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            return

        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Register callbacks and copy the wrapped entity's custom name if set."""

        @callback
        def _async_state_changed_listener(
            event: Event[EventStateChangedData] | None = None,
        ) -> None:
            """Handle child updates."""
            self.async_state_changed_listener(event)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._binary_sensor_entity_id],
                _async_state_changed_listener,
            )
        )

        # Call once on adding
        _async_state_changed_listener()

        # Update entity options
        registry = er.async_get(self.hass)
        if registry.async_get(self.entity_id) is not None:
            registry.async_update_entity_options(
                self.entity_id,
                BINARY_SENSOR_AS_X_DOMAIN,
                self.async_generate_entity_options(),
            )

        if not self._is_new_entity or not (
            wrapped_binary_sensor := registry.async_get(self._binary_sensor_entity_id)
        ):
            return

        def copy_custom_name(wrapped_binary_sensor: er.RegistryEntry) -> None:
            """Copy the name set by user from the wrapped entity."""
            if wrapped_binary_sensor.name is None:
                return
            registry.async_update_entity(
                self.entity_id, name=wrapped_binary_sensor.name
            )

        def copy_expose_settings() -> None:
            """Copy assistant expose settings from the wrapped entity.

            Also unexpose the wrapped entity if exposed.
            """
            expose_settings = exposed_entities.async_get_entity_settings(
                self.hass, self._binary_sensor_entity_id
            )
            for assistant, settings in expose_settings.items():
                if (should_expose := settings.get("should_expose")) is None:
                    continue
                exposed_entities.async_expose_entity(
                    self.hass, assistant, self.entity_id, should_expose
                )
                exposed_entities.async_expose_entity(
                    self.hass, assistant, self._binary_sensor_entity_id, False
                )

        copy_custom_name(wrapped_binary_sensor)
        copy_expose_settings()

    @callback
    def async_generate_entity_options(self) -> dict[str, Any]:
        """Generate entity options."""
        return {"entity_id": self._binary_sensor_entity_id}


class BaseDeviceClassEntity(BaseEntity):
    """Represents a Binary sensor as X where the device_class is important."""

    _accepted_device_classes: type[StrEnum] | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_title: str,
        domain: str,
        binary_sensor_entity_id: str,
        unique_id: str,
    ) -> None:
        """Initialize Binary sensor as an X and inherit device_class."""
        super().__init__(
            hass, config_entry_title, domain, binary_sensor_entity_id, unique_id
        )

        try:
            # Don't fail if the entity doesn't exist
            if device_class := get_device_class(hass, binary_sensor_entity_id):
                if (
                    not self._accepted_device_classes
                    or device_class in self._accepted_device_classes
                ):
                    self._attr_device_class = device_class
        except HomeAssistantError:
            pass
