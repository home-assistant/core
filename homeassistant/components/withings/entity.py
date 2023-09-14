"""Base entity for Withings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from withings_api.common import GetSleepSummaryField, MeasureType, NotifyAppli

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    BaseWithingsDataUpdateCoordinator,
    PollingWithingsDataUpdateCoordinator,
    WebhookWithingsDataUpdateCoordinator,
)
from .const import DOMAIN, Measurement

_BaseWithingsDataUpdateCoordinatorT = TypeVar(
    "_BaseWithingsDataUpdateCoordinatorT", bound="BaseWithingsDataUpdateCoordinator"
)


@dataclass
class WithingsEntityDescriptionMixin:
    """Mixin for describing withings data."""

    measurement: Measurement
    measure_type: NotifyAppli | GetSleepSummaryField | MeasureType


@dataclass
class WithingsEntityDescription(EntityDescription, WithingsEntityDescriptionMixin):
    """Immutable class for describing withings data."""


class BaseWithingsEntity(CoordinatorEntity[_BaseWithingsDataUpdateCoordinatorT]):
    """Base class for withings sensors."""

    entity_description: WithingsEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _BaseWithingsDataUpdateCoordinatorT,
        description: WithingsEntityDescription,
    ) -> None:
        """Initialize the Withings sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"withings_{coordinator.config_entry.unique_id}_{description.measurement.value}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.config_entry.unique_id))},
            manufacturer="Withings",
        )


class PollingWithingsEntity(BaseWithingsEntity[PollingWithingsDataUpdateCoordinator]):
    """Sensor used for polling."""


class WebhookWithingsEntity(BaseWithingsEntity[WebhookWithingsDataUpdateCoordinator]):
    """Sensor used for Webhooks."""

    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Register update dispatcher."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
