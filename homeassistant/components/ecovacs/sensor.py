"""Ecovacs sensor module."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import floor
from typing import Any, Generic

from deebot_client.capabilities import CapabilityEvent, CapabilityLifeSpan
from deebot_client.device import Device
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

from .const import DOMAIN
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
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    EcovacsSensorEntityDescription[StatsEvent](
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: e.type,
        key="stats_type",
        translation_key="stats_type",
    ),
    # TotalStats
    EcovacsSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.area,
        key="stats_total_area",
        translation_key="stats_total_area",
        native_unit_of_measurement=AREA_SQUARE_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcovacsSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: round(e.time / 3600),
        key="stats_total_time",
        translation_key="stats_total_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcovacsSensorEntityDescription[TotalStatsEvent](
        capability_fn=lambda caps: caps.stats.total,
        value_fn=lambda e: e.cleanings,
        key="stats_total_cleanings",
        translation_key="stats_total_cleanings",
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
        key="wifi_ip",
        translation_key="wifi_ip",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EcovacsSensorEntityDescription[NetworkInfoEvent](
        capability_fn=lambda caps: caps.network,
        value_fn=lambda e: e.rssi,
        key="wifi_rssi",
        translation_key="wifi_rssi",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EcovacsSensorEntityDescription[NetworkInfoEvent](
        capability_fn=lambda caps: caps.network,
        value_fn=lambda e: e.ssid,
        key="wifi_ssid",
        translation_key="wifi_ssid",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


_SUPPORTED_LIFE_SPAN_TYPES = (
    LifeSpan.BRUSH,
    LifeSpan.FILTER,
    LifeSpan.SIDE_BRUSH,
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
        for component in _SUPPORTED_LIFE_SPAN_TYPES:
            if component in lifespan_capability.types:
                entities.append(
                    EcovacsLifeSpanSensor(device, lifespan_capability, component)
                )

        if capability := device.capabilities.error:
            entities.append(EcovacsLastErrorSensor(device, capability))

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


class EcovacsLifeSpanSensor(
    EcovacsDescriptionEntity[CapabilityLifeSpan],
    SensorEntity,
):
    """Life span sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        device: Device,
        capability: CapabilityLifeSpan,
        component: LifeSpan,
        **kwargs: Any,
    ) -> None:
        """Initialize entity."""
        key = f"life_span_{component.name.lower()}"
        super().__init__(
            device,
            capability,
            SensorEntityDescription(
                key=key,
                translation_key=key,
                native_unit_of_measurement=PERCENTAGE,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            **kwargs,
        )
        self._component = component

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: LifeSpanEvent) -> None:
            if event.type == self._component:
                self._attr_native_value = event.percent
                self._attr_extra_state_attributes = {
                    "remaining": floor(event.remaining / 60)
                }
                self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)


class EcovacsLastErrorSensor(
    EcovacsEntity[CapabilityEvent[ErrorEvent]],
    SensorEntity,
):
    """Last error sensor."""

    _always_available = True
    _unrecorded_attributes = frozenset({CONF_DESCRIPTION})
    entity_description: SensorEntityDescription = SensorEntityDescription(
        key="last_error",
        translation_key="last_error",
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
