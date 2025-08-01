"""Ecovacs sensor module."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from deebot_client.capabilities import CapabilityEvent, CapabilityLifeSpan, DeviceType
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
    station,
)
from sucks import VacBot

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_DESCRIPTION,
    PERCENTAGE,
    EntityCategory,
    UnitOfArea,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import StateType

from . import EcovacsConfigEntry
from .const import LEGACY_SUPPORTED_LIFESPANS, SUPPORTED_LIFESPANS
from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
    EcovacsLegacyEntity,
)
from .util import get_name_key, get_options, get_supported_entities


@dataclass(kw_only=True, frozen=True)
class EcovacsSensorEntityDescription[EventT: Event](
    EcovacsCapabilityEntityDescription,
    SensorEntityDescription,
):
    """Ecovacs sensor entity description."""

    value_fn: Callable[[EventT], StateType]
    native_unit_of_measurement_fn: Callable[[DeviceType], str | None] | None = None


@callback
def get_area_native_unit_of_measurement(device_type: DeviceType) -> str | None:
    """Get the area native unit of measurement based on device type."""
    if device_type is DeviceType.MOWER:
        return UnitOfArea.SQUARE_CENTIMETERS
    return UnitOfArea.SQUARE_METERS


ENTITY_DESCRIPTIONS: tuple[EcovacsSensorEntityDescription, ...] = (
    # Stats
    EcovacsSensorEntityDescription[StatsEvent](
        key="stats_area",
        capability_fn=lambda caps: caps.stats.clean,
        value_fn=lambda e: e.area,
        translation_key="stats_area",
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement_fn=get_area_native_unit_of_measurement,
        suggested_unit_of_measurement=UnitOfArea.SQUARE_METERS,
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
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
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
    # Station
    EcovacsSensorEntityDescription[station.StationEvent](
        capability_fn=lambda caps: caps.station.state if caps.station else None,
        value_fn=lambda e: get_name_key(e.state),
        key="station_state",
        translation_key="station_state",
        device_class=SensorDeviceClass.ENUM,
        options=get_options(station.State),
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


@dataclass(kw_only=True, frozen=True)
class EcovacsLegacyLifespanSensorEntityDescription(SensorEntityDescription):
    """Ecovacs lifespan sensor entity description."""

    component: str


LEGACY_LIFESPAN_SENSORS = tuple(
    EcovacsLegacyLifespanSensorEntityDescription(
        component=component,
        key=f"lifespan_{component}",
        translation_key=f"lifespan_{component}",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    for component in LEGACY_SUPPORTED_LIFESPANS
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data

    entities: list[EcovacsEntity] = get_supported_entities(
        controller, EcovacsSensor, ENTITY_DESCRIPTIONS
    )
    entities.extend(
        EcovacsLifespanSensor(device, device.capabilities.life_span, description)
        for device in controller.devices
        for description in LIFESPAN_ENTITY_DESCRIPTIONS
        if description.component in device.capabilities.life_span.types
    )
    entities.extend(
        EcovacsErrorSensor(device, capability)
        for device in controller.devices
        if (capability := device.capabilities.error)
    )

    async_add_entities(entities)

    async def _add_legacy_lifespan_entities() -> None:
        entities = []
        for device in controller.legacy_devices:
            for description in LEGACY_LIFESPAN_SENSORS:
                if (
                    description.component in device.components
                    and not controller.legacy_entity_is_added(
                        device, description.component
                    )
                ):
                    controller.add_legacy_entity(device, description.component)
                    entities.append(EcovacsLegacyLifespanSensor(device, description))

        if entities:
            async_add_entities(entities)

    def _fire_ecovacs_legacy_lifespan_event(_: Any) -> None:
        hass.create_task(_add_legacy_lifespan_entities())

    legacy_entities = []
    for device in controller.legacy_devices:
        config_entry.async_on_unload(
            device.lifespanEvents.subscribe(
                _fire_ecovacs_legacy_lifespan_event
            ).unsubscribe
        )
        if not controller.legacy_entity_is_added(device, "battery_status"):
            controller.add_legacy_entity(device, "battery_status")
            legacy_entities.append(EcovacsLegacyBatterySensor(device))

    if legacy_entities:
        async_add_entities(legacy_entities)


class EcovacsSensor(
    EcovacsDescriptionEntity[CapabilityEvent],
    SensorEntity,
):
    """Ecovacs sensor."""

    entity_description: EcovacsSensorEntityDescription

    def __init__(
        self,
        device: Device,
        capability: CapabilityEvent,
        entity_description: EcovacsSensorEntityDescription,
        **kwargs: Any,
    ) -> None:
        """Initialize entity."""
        super().__init__(device, capability, entity_description, **kwargs)
        if (
            entity_description.native_unit_of_measurement_fn
            and (
                native_unit_of_measurement
                := entity_description.native_unit_of_measurement_fn(
                    device.capabilities.device_type
                )
            )
            is not None
        ):
            self._attr_native_unit_of_measurement = native_unit_of_measurement

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


class EcovacsLegacyBatterySensor(EcovacsLegacyEntity, SensorEntity):
    """Legacy battery sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        device: VacBot,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self._attr_unique_id = f"{device.vacuum['did']}_battery_status"

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        self._event_listeners.append(
            self.device.batteryEvents.subscribe(
                lambda _: self.schedule_update_ha_state()
            )
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        if (status := self.device.battery_status) is not None:
            return status * 100  # type: ignore[no-any-return]
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        return icon_for_battery_level(
            battery_level=self.native_value, charging=self.device.is_charging
        )


class EcovacsLegacyLifespanSensor(EcovacsLegacyEntity, SensorEntity):
    """Legacy Lifespan sensor."""

    entity_description: EcovacsLegacyLifespanSensorEntityDescription

    def __init__(
        self,
        device: VacBot,
        description: EcovacsLegacyLifespanSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{device.vacuum['did']}_{description.key}"

        if (value := device.components.get(description.component)) is not None:
            value = int(value * 100)
        self._attr_native_value = value

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""

        def on_event(_: Any) -> None:
            if (
                value := self.device.components.get(self.entity_description.component)
            ) is not None:
                value = int(value * 100)
            self._attr_native_value = value
            self.schedule_update_ha_state()

        self._event_listeners.append(self.device.lifespanEvents.subscribe(on_event))
