"""Ecovacs sensor module."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from deebot_client.capabilities import CapabilityEvent, CapabilityLifeSpan
from deebot_client.events import (
    BatteryEvent,
    ErrorEvent,
    Event,
    LifeSpan,
    LifeSpanEvent,
    NetworkInfoEvent,
    StatsEvent,
    TotalStatsEvent,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    ATTR_BATTERY_LEVEL,
    CONF_DESCRIPTION,
    PERCENTAGE,
    EntityCategory,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, SUPPORTED_LIFESPANS
from .controller import EcovacsController
from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
    EventT,
)
from .util import get_supported_entitites


@dataclass(kw_only=True, frozen=True)
class EcovacsSensorEntityDescription(
    EcovacsCapabilityEntityDescription,
    SensorEntityDescription,
    Generic[EventT],
):
    """Ecovacs sensor entity description."""

    value_fn: Callable[[EventT], StateType]


ENTITY_DESCRIPTIONS: tuple[EcovacsSensorEntityDescription, ...] = (
    # Stats
    EcovacsSensorEntityDescription[StatsEvent](
        key="stats_area",
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: e.area,
        translation_key="stats_area",
        native_unit_of_measurement=AREA_SQUARE_METERS,
    ),
    EcovacsSensorEntityDescription[StatsEvent](
        key="stats_time",
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: e.time,
        translation_key="stats_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    # TotalStats
    EcovacsSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.area,
        key="total_stats_area",
        translation_key="total_stats_area",
        native_unit_of_measurement=AREA_SQUARE_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcovacsSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.time,
        key="total_stats_time",
        translation_key="total_stats_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcovacsSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.cleanings,
        key="total_stats_cleanings",
        translation_key="total_stats_cleanings",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcovacsSensorEntityDescription[BatteryEvent](
        capability_fn=lambda caps: caps.battery,
        value_fn=lambda e: e.value,
        key=ATTR_BATTERY_LEVEL,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EcovacsSensorEntityDescription[NetworkInfoEvent](
        capability_fn=lambda caps: caps.network,
        value_fn=lambda e: e.ip,
        key="network_ip",
        translation_key="network_ip",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EcovacsSensorEntityDescription[NetworkInfoEvent](
        capability_fn=lambda caps: caps.network,
        value_fn=lambda e: e.rssi,
        key="network_rssi",
        translation_key="network_rssi",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EcovacsSensorEntityDescription[NetworkInfoEvent](
        capability_fn=lambda caps: caps.network,
        value_fn=lambda e: e.ssid,
        key="network_ssid",
        translation_key="network_ssid",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


@dataclass(kw_only=True, frozen=True)
class EcovacsLifespanSensorEntityDescription(SensorEntityDescription):
    """Ecovacs lifespan sensor entity description."""

    component: LifeSpan
    value_fn: Callable[[LifeSpanEvent], int | float]


LIFESPAN_ENTITY_DESCRIPTIONS = tuple(
    EcovacsLifespanSensorEntityDescription(
        component=component,
        value_fn=lambda e: e.percent,
        key=f"lifespan_{component.name.lower()}",
        translation_key=f"lifespan_{component.name.lower()}",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    for component in SUPPORTED_LIFESPANS
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller: EcovacsController = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[EcovacsEntity] = get_supported_entitites(
        controller, EcovacsSensor, ENTITY_DESCRIPTIONS
    )
    for device in controller.devices:
        lifespan_capability = device.capabilities.life_span
        for description in LIFESPAN_ENTITY_DESCRIPTIONS:
            if description.component in lifespan_capability.types:
                entities.append(
                    EcovacsLifespanSensor(device, lifespan_capability, description)
                )

        if capability := device.capabilities.error:
            entities.append(EcovacsErrorSensor(device, capability))

    async_add_entities(entities)


class EcovacsSensor(
    EcovacsDescriptionEntity[CapabilityEvent],
    SensorEntity,
):
    """Ecovacs sensor."""

    entity_description: EcovacsSensorEntityDescription

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: Event) -> None:
            value = self.entity_description.value_fn(event)
            if value is None:
                return

            self._attr_native_value = value
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)


class EcovacsLifespanSensor(
    EcovacsDescriptionEntity[CapabilityLifeSpan],
    SensorEntity,
):
    """Lifespan sensor."""

    entity_description: EcovacsLifespanSensorEntityDescription

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: LifeSpanEvent) -> None:
            if event.type == self.entity_description.component:
                self._attr_native_value = self.entity_description.value_fn(event)
                self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)


class EcovacsErrorSensor(
    EcovacsEntity[CapabilityEvent[ErrorEvent]],
    SensorEntity,
):
    """Error sensor."""

    _always_available = True
    _unrecorded_attributes = frozenset({CONF_DESCRIPTION})
    entity_description: SensorEntityDescription = SensorEntityDescription(
        key="error",
        translation_key="error",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: ErrorEvent) -> None:
            self._attr_native_value = event.code
            self._attr_extra_state_attributes = {CONF_DESCRIPTION: event.description}

            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)
