"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from simplefin4py import Account
from simplefin4py.model import AccountType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpleFinConfigEntry
from .entity import SimpleFinEntity


@dataclass(frozen=True, kw_only=True)
class SimpleFinSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor entity."""

    value_fn: Callable[[Account], int | str | datetime | None]
    icon_fn: Callable[[AccountType], str] | None = None
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

    runtime_data = config_entry.runtime_data
    accounts = config_entry.runtime_data.sf_coordinator.data.accounts

    async_add_entities(
        SimpleFinSensor(
            runtime_data.sf_coordinator,
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
    def account_data(self) -> Account:
        """Return the account data."""
        return self.coordinator.data.get_account_for_id(self._account_id)

    @property
    def native_value(self) -> int | str | datetime | None:
        """Return the state."""
        return self.entity_description.value_fn(self.account_data)

    @property
    def icon(self) -> str | None:
        """Return the icon of this account."""

        if not (icon_fn := getattr(self.entity_description, "icon_fn", None)):
            return None

        return icon_fn(self.coordinator.data.get_account_for_id(self._account_id))

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency of this account."""
        if self.entity_description.unit_fn:
            return self.entity_description.unit_fn(self.account_data)

        return None
