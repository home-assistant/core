"""Base entity for the Inverse integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.homeassistant import exposed_entities
from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN


class BaseEntity(Entity):
    """Represents an Inverse entity."""

    _attr_should_poll = False
    _is_new_entity: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_title: str,
        domain: str,
        source_entity_id: str,
        unique_id: str,
    ) -> None:
        """Initialize Inverse entity."""
        registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        wrapped_entity = registry.async_get(source_entity_id)
        device_id = wrapped_entity.device_id if wrapped_entity else None
        entity_category = wrapped_entity.entity_category if wrapped_entity else None
        has_entity_name = wrapped_entity.has_entity_name if wrapped_entity else False

        name: str | None = config_entry_title
        if wrapped_entity:
            name = wrapped_entity.original_name

        if device_id and (device := device_registry.async_get(device_id)):
            self.device_entry = device
        self._attr_entity_category = entity_category
        self._attr_has_entity_name = has_entity_name
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._source_entity_id = source_entity_id
        self._source_domain = source_entity_id.split(".")[0]

        source_object_id = (
            source_entity_id.split(".", 1)[1]
            if "." in source_entity_id
            else source_entity_id
        )
        self._attr_entity_id = f"{domain}.inverse_{source_object_id}"

        self._is_new_entity = (
            registry.async_get_entity_id(domain, DOMAIN, unique_id) is None
        )

    @callback
    def async_state_changed_listener(
        self, event: Event[EventStateChangedData] | None = None
    ) -> None:
        """Handle child updates."""
        if (
            state := self.hass.states.get(self._source_entity_id)
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
                self.hass, [self._source_entity_id], _async_state_changed_listener
            )
        )

        # Call once on adding
        _async_state_changed_listener()

        # Update entity options
        registry = er.async_get(self.hass)
        if registry.async_get(self.entity_id) is not None:
            registry.async_update_entity_options(
                self.entity_id,
                DOMAIN,
                self.async_generate_entity_options(),
            )

        if not self._is_new_entity or not (
            wrapped_entity := registry.async_get(self._source_entity_id)
        ):
            return

        def copy_custom_name(wrapped_entity: er.RegistryEntry) -> None:
            """Copy the name set by user from the wrapped entity."""
            if wrapped_entity.name is None:
                return
            registry.async_update_entity(self.entity_id, name=wrapped_entity.name)

        def copy_expose_settings() -> None:
            """Copy assistant expose settings from the wrapped entity.

            Also unexpose the wrapped entity if exposed.
            """
            # In some test contexts, the exposed entities store is not initialized.
            if DATA_EXPOSED_ENTITIES not in self.hass.data:
                return

            expose_settings = exposed_entities.async_get_entity_settings(
                self.hass, self._source_entity_id
            )
            for assistant, settings in expose_settings.items():
                if (should_expose := settings.get("should_expose")) is None:
                    continue
                exposed_entities.async_expose_entity(
                    self.hass, assistant, self.entity_id, should_expose
                )
                exposed_entities.async_expose_entity(
                    self.hass, assistant, self._source_entity_id, False
                )

        copy_custom_name(wrapped_entity)
        copy_expose_settings()

    @callback
    def async_generate_entity_options(self) -> dict[str, Any]:
        """Generate entity options."""
        return {"entity_id": self._source_entity_id}


class BaseToggleEntity(BaseEntity, ToggleEntity):
    """Represents a ToggleEntity wrapper."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to the source entity."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward the turn_off command to the source entity."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    @callback
    def async_state_changed_listener(
        self, event: Event[EventStateChangedData] | None = None
    ) -> None:
        """Handle child updates."""
        super().async_state_changed_listener(event)
        if (
            not self.available
            or (state := self.hass.states.get(self._source_entity_id)) is None
        ):
            return

        self._attr_is_on = state.state == STATE_ON


class BaseInverseEntity(BaseEntity):
    """Represents an Inverse entity that always inverts state."""
