"""Base entity for Withings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from withings_api.common import GetSleepSummaryField, MeasureType, NotifyAppli

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .common import DataManager, UpdateType
from .const import DOMAIN, Measurement


@dataclass
class WithingsEntityDescriptionMixin:
    """Mixin for describing withings data."""

    measurement: Measurement
    measure_type: NotifyAppli | GetSleepSummaryField | MeasureType
    update_type: UpdateType


@dataclass
class WithingsEntityDescription(EntityDescription, WithingsEntityDescriptionMixin):
    """Immutable class for describing withings data."""


class BaseWithingsSensor(Entity):
    """Base class for withings sensors."""

    _attr_should_poll = False
    entity_description: WithingsEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, data_manager: DataManager, description: WithingsEntityDescription
    ) -> None:
        """Initialize the Withings sensor."""
        self._data_manager = data_manager
        self.entity_description = description
        self._attr_unique_id = (
            f"withings_{data_manager.user_id}_{description.measurement.value}"
        )
        self._state_data: Any | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(data_manager.user_id))}, manufacturer="Withings"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.entity_description.update_type == UpdateType.POLL:
            return self._data_manager.poll_data_update_coordinator.last_update_success

        if self.entity_description.update_type == UpdateType.WEBHOOK:
            return self._data_manager.webhook_config.enabled and (
                self.entity_description.measurement
                in self._data_manager.webhook_update_coordinator.data
            )

        return True

    @callback
    def _on_poll_data_updated(self) -> None:
        self._update_state_data(
            self._data_manager.poll_data_update_coordinator.data or {}
        )

    @callback
    def _on_webhook_data_updated(self) -> None:
        self._update_state_data(
            self._data_manager.webhook_update_coordinator.data or {}
        )

    def _update_state_data(self, data: dict[Measurement, Any]) -> None:
        """Update the state data."""
        self._state_data = data.get(self.entity_description.measurement)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register update dispatcher."""
        if self.entity_description.update_type == UpdateType.POLL:
            self.async_on_remove(
                self._data_manager.poll_data_update_coordinator.async_add_listener(
                    self._on_poll_data_updated
                )
            )
            self._on_poll_data_updated()

        elif self.entity_description.update_type == UpdateType.WEBHOOK:
            self.async_on_remove(
                self._data_manager.webhook_update_coordinator.async_add_listener(
                    self._on_webhook_data_updated
                )
            )
            self._on_webhook_data_updated()
