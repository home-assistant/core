"""Sensor platform for the Eve Online integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    EveOnlineConfigEntry,
    EveOnlineCoordinator,
    EveOnlineData,
    EveOnlineIndustryCoordinator,
    EveOnlineIndustryData,
    EveOnlineMarketCoordinator,
    EveOnlineMarketData,
    EveOnlineSkillsCoordinator,
    EveOnlineSkillsData,
)
from .entity import EveOnlineCharacterEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EveOnlineSensorDescription(SensorEntityDescription):
    """Describe a fast Eve Online sensor (60 s)."""

    value_fn: Callable[[EveOnlineData], str | int | float | datetime | None]


@dataclass(frozen=True, kw_only=True)
class EveOnlineIndustrySensorDescription(SensorEntityDescription):
    """Describe an industry/fatigue Eve Online sensor (300 s)."""

    value_fn: Callable[[EveOnlineIndustryData], str | int | float | datetime | None]


@dataclass(frozen=True, kw_only=True)
class EveOnlineMarketSensorDescription(SensorEntityDescription):
    """Describe a market Eve Online sensor (3600 s)."""

    value_fn: Callable[[EveOnlineMarketData], str | int | float | datetime | None]


@dataclass(frozen=True, kw_only=True)
class EveOnlineSkillsSensorDescription(SensorEntityDescription):
    """Describe a skills Eve Online sensor (86400 s)."""

    value_fn: Callable[[EveOnlineSkillsData], str | int | float | datetime | None]


FAST_SENSORS: tuple[EveOnlineSensorDescription, ...] = (
    EveOnlineSensorDescription(
        key="location",
        translation_key="location",
        value_fn=lambda data: (
            data.resolved_names.get(
                data.location.solar_system_id,
                str(data.location.solar_system_id),
            )
            if data.location
            else None
        ),
    ),
    EveOnlineSensorDescription(
        key="ship",
        translation_key="ship",
        value_fn=lambda data: (
            data.resolved_names.get(data.ship.ship_type_id, str(data.ship.ship_type_id))
            if data.ship
            else None
        ),
    ),
    EveOnlineSensorDescription(
        key="wallet_balance",
        translation_key="wallet_balance",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.wallet_balance.balance if data.wallet_balance else None
        ),
    ),
    EveOnlineSensorDescription(
        key="unread_mail",
        translation_key="unread_mail",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.mail_labels.total_unread_count if data.mail_labels else None
        ),
    ),
)

INDUSTRY_SENSORS: tuple[EveOnlineIndustrySensorDescription, ...] = (
    EveOnlineIndustrySensorDescription(
        key="skill_queue_count",
        translation_key="skill_queue_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(data.skill_queue),
    ),
    EveOnlineIndustrySensorDescription(
        key="current_training_skill",
        translation_key="current_training_skill",
        value_fn=lambda data: (
            data.resolved_names.get(
                data.skill_queue[0].skill_id,
                str(data.skill_queue[0].skill_id),
            )
            + f" {data.skill_queue[0].finished_level}"
            if data.skill_queue
            else None
        ),
    ),
    EveOnlineIndustrySensorDescription(
        key="current_skill_finish",
        translation_key="current_skill_finish",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (
            data.skill_queue[0].finish_date
            if data.skill_queue and data.skill_queue[0].finish_date
            else None
        ),
    ),
    EveOnlineIndustrySensorDescription(
        key="industry_jobs",
        translation_key="industry_jobs",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(
            1 for j in data.industry_jobs if j.status == "active"
        ),
    ),
    EveOnlineIndustrySensorDescription(
        key="next_industry_finish",
        translation_key="next_industry_finish",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: min(
            (j.end_date for j in data.industry_jobs if j.status == "active"),
            default=None,
        ),
    ),
    EveOnlineIndustrySensorDescription(
        key="jump_fatigue",
        translation_key="jump_fatigue",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (
            data.jump_fatigue.jump_fatigue_expire_date
            if data.jump_fatigue and data.jump_fatigue.jump_fatigue_expire_date
            else None
        ),
    ),
)

MARKET_SENSORS: tuple[EveOnlineMarketSensorDescription, ...] = (
    EveOnlineMarketSensorDescription(
        key="sell_orders",
        translation_key="sell_orders",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(1 for o in data.market_orders if not o.is_buy_order),
    ),
    EveOnlineMarketSensorDescription(
        key="buy_orders",
        translation_key="buy_orders",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(1 for o in data.market_orders if o.is_buy_order),
    ),
)

SKILLS_SENSORS: tuple[EveOnlineSkillsSensorDescription, ...] = (
    EveOnlineSkillsSensorDescription(
        key="total_sp",
        translation_key="total_sp",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.skills.total_sp if data.skills else None,
    ),
    EveOnlineSkillsSensorDescription(
        key="unallocated_sp",
        translation_key="unallocated_sp",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.skills.unallocated_sp if data.skills else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EveOnlineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eve Online sensors from a config entry."""
    runtime_data = entry.runtime_data
    async_add_entities(
        [
            *(
                EveOnlineCharacterSensor(runtime_data.coordinator, description)
                for description in FAST_SENSORS
            ),
            *(
                EveOnlineIndustrySensor(runtime_data.industry_coordinator, description)
                for description in INDUSTRY_SENSORS
            ),
            *(
                EveOnlineMarketSensor(runtime_data.market_coordinator, description)
                for description in MARKET_SENSORS
            ),
            *(
                EveOnlineSkillsSensor(runtime_data.skills_coordinator, description)
                for description in SKILLS_SENSORS
            ),
        ]
    )


class EveOnlineCharacterSensor(
    EveOnlineCharacterEntity[EveOnlineCoordinator], SensorEntity
):
    """Fast-polling Eve Online sensor (location, ship, wallet, mail)."""

    entity_description: EveOnlineSensorDescription

    def __init__(
        self,
        coordinator: EveOnlineCoordinator,
        description: EveOnlineSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class EveOnlineIndustrySensor(
    EveOnlineCharacterEntity[EveOnlineIndustryCoordinator], SensorEntity
):
    """Industry jobs and jump-fatigue Eve Online sensor."""

    entity_description: EveOnlineIndustrySensorDescription

    def __init__(
        self,
        coordinator: EveOnlineIndustryCoordinator,
        description: EveOnlineIndustrySensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class EveOnlineMarketSensor(
    EveOnlineCharacterEntity[EveOnlineMarketCoordinator], SensorEntity
):
    """Market orders Eve Online sensor."""

    entity_description: EveOnlineMarketSensorDescription

    def __init__(
        self,
        coordinator: EveOnlineMarketCoordinator,
        description: EveOnlineMarketSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class EveOnlineSkillsSensor(
    EveOnlineCharacterEntity[EveOnlineSkillsCoordinator], SensorEntity
):
    """Character skills / SP Eve Online sensor."""

    entity_description: EveOnlineSkillsSensorDescription

    def __init__(
        self,
        coordinator: EveOnlineSkillsCoordinator,
        description: EveOnlineSkillsSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
