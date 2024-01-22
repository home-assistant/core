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
from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkHostCoordinatorEntity,
    ReolinkHostEntityDescription,
)


@dataclass(frozen=True, kw_only=True)
class ReolinkSensorEntityDescription(
    SensorEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes sensor entities for a camera channel."""

    value: Callable[[Host, int], int]


@dataclass(frozen=True, kw_only=True)
class ReolinkHostSensorEntityDescription(
    SensorEntityDescription,
    ReolinkHostEntityDescription,
):
    """A class that describes host sensor entities."""

    value: Callable[[Host], int | None]


SENSORS = (
    ReolinkSensorEntityDescription(
        key="ptz_pan_position",
        cmd_key="GetPtzCurPos",
        translation_key="ptz_pan_position",
        icon="mdi:pan",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda api, ch: api.ptz_pan_position(ch),
        supported=lambda api, ch: api.supported(ch, "ptz_position"),
    ),
)

HOST_SENSORS = (
    ReolinkHostSensorEntityDescription(
        key="wifi_signal",
        cmd_key="GetWifiSignal",
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

    entities: list[ReolinkSensorEntity | ReolinkHostSensorEntity] = [
        ReolinkSensorEntity(reolink_data, channel, entity_description)
        for entity_description in SENSORS
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        [
            ReolinkHostSensorEntity(reolink_data, entity_description)
            for entity_description in HOST_SENSORS
            if entity_description.supported(reolink_data.host.api)
        ]
    )
    async_add_entities(entities)


class ReolinkSensorEntity(ReolinkChannelCoordinatorEntity, SensorEntity):
    """Base sensor class for Reolink IP camera sensors."""

    entity_description: ReolinkSensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkSensorEntityDescription,
    ) -> None:
        """Initialize Reolink sensor."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self._host.api, self._channel)


class ReolinkHostSensorEntity(ReolinkHostCoordinatorEntity, SensorEntity):
    """Base sensor class for Reolink host sensors."""

    entity_description: ReolinkHostSensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostSensorEntityDescription,
    ) -> None:
        """Initialize Reolink host sensor."""
        self.entity_description = entity_description
        super().__init__(reolink_data)

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self._host.api)
