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

from .coordinator import EveOnlineConfigEntry, EveOnlineCoordinator, EveOnlineData
from .entity import EveOnlineCharacterEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EveOnlineSensorDescription(SensorEntityDescription):
    """Describe an Eve Online sensor."""

    value_fn: Callable[[EveOnlineData], str | int | float | datetime | None]


CHARACTER_SENSORS: tuple[EveOnlineSensorDescription, ...] = (
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
        key="total_sp",
        translation_key="total_sp",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.skills.total_sp if data.skills else None,
    ),
    EveOnlineSensorDescription(
        key="unallocated_sp",
        translation_key="unallocated_sp",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.skills.unallocated_sp if data.skills else None,
    ),
    EveOnlineSensorDescription(
        key="skill_queue_count",
        translation_key="skill_queue_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(data.skill_queue),
    ),
    EveOnlineSensorDescription(
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
    EveOnlineSensorDescription(
        key="current_skill_finish",
        translation_key="current_skill_finish",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (
            data.skill_queue[0].finish_date
            if data.skill_queue and data.skill_queue[0].finish_date
            else None
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
    EveOnlineSensorDescription(
        key="industry_jobs",
        translation_key="industry_jobs",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(
            1 for j in data.industry_jobs if j.status == "active"
        ),
    ),
    EveOnlineSensorDescription(
        key="next_industry_finish",
        translation_key="next_industry_finish",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: min(
            (j.end_date for j in data.industry_jobs if j.status == "active"),
            default=None,
        ),
    ),
    EveOnlineSensorDescription(
        key="sell_orders",
        translation_key="sell_orders",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(1 for o in data.market_orders if not o.is_buy_order),
    ),
    EveOnlineSensorDescription(
        key="buy_orders",
        translation_key="buy_orders",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: sum(1 for o in data.market_orders if o.is_buy_order),
    ),
    EveOnlineSensorDescription(
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EveOnlineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eve Online sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        EveOnlineCharacterSensor(coordinator, description)
        for description in CHARACTER_SENSORS
    )


class EveOnlineCharacterSensor(EveOnlineCharacterEntity, SensorEntity):
    """Eve Online character sensor (per-character device)."""

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
