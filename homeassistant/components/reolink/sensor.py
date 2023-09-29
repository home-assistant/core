"""Component providing support for Reolink sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from reolink_aio.api import Host

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import ReolinkData
from .const import DOMAIN
from .entity import ReolinkHostCoordinatorEntity


@dataclass
class ReolinkHostSensorEntityDescriptionMixin:
    """Mixin values for Reolink host sensor entities."""

    value: Callable[[Host], bool]


@dataclass
class ReolinkHostSensorEntityDescription(
    SensorEntityDescription, ReolinkHostSensorEntityDescriptionMixin
):
    """A class that describes host sensor entities."""

    supported: Callable[[Host], bool] = lambda host: True


HOST_SENSORS = (
    ReolinkHostSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        icon="mdi:wifi",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda api: api.wifi_signal,
        supported=lambda api: api.supported(None, "wifi") and api.wifi_connection,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ReolinkHostSensorEntity(reolink_data, entity_description)
        for entity_description in HOST_SENSORS
        if entity_description.supported(reolink_data.host.api)
    )


class ReolinkHostSensorEntity(ReolinkHostCoordinatorEntity, SensorEntity):
    """Base sensor class for Reolink host sensors."""

    entity_description: ReolinkHostSensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostSensorEntityDescription,
    ) -> None:
        """Initialize Reolink binary sensor."""
        super().__init__(reolink_data)
        self.entity_description = entity_description

        self._attr_unique_id = f"{self._host.unique_id}_{entity_description.key}"

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self._host.api)
