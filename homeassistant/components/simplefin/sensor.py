"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from simplefin4py import Account

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SimpleFinConfigEntry
from .entity import SimpleFinEntity


@dataclass(frozen=True, kw_only=True)
class SimpleFinSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor entity."""

    value_fn: Callable[[Account], StateType]
    icon_fn: Callable[[Account], str] | None = None
    unit_fn: Callable[[Account], str] | None = None


SIMPLEFIN_SENSORS: tuple[SimpleFinSensorEntityDescription, ...] = (
    SimpleFinSensorEntityDescription(
        key="balance",
        translation_key="balance",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda account: account.balance,
        unit_fn=lambda account: account.currency,
        icon_fn=lambda account: account.inferred_account_type,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SimpleFinConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SimpleFIN sensors for config entries."""

    sf_coordinator = config_entry.runtime_data
    accounts = sf_coordinator.data.accounts

    async_add_entities(
        SimpleFinSensor(
            sf_coordinator,
            sensor_description,
            account,
        )
        for account in accounts
        for sensor_description in SIMPLEFIN_SENSORS
    )


class SimpleFinSensor(SimpleFinEntity, SensorEntity):
    """Defines a SimpleFIN sensor."""

    entity_description: SimpleFinSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.account_data)

    @property
    def icon(self) -> str | None:
        """Return the icon of this account."""

        if self.entity_description.icon_fn is not None:
            return self.entity_description.icon_fn(self.account_data)
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency of this account."""
        if self.entity_description.unit_fn:
            return self.entity_description.unit_fn(self.account_data)

        return None
