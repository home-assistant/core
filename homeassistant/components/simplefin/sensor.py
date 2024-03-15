"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from simplefin4py import Account

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SimpleFinDataUpdateCoordinator
from .entity import SimpleFinEntity


@dataclass(frozen=True, kw_only=True)
class SimpleFinSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor entity."""

    value_fn: Callable[[Account], int | str | datetime | None]

    icon_fn: Callable[[Account], str] | None = None
    unit_fn: Callable[[Account], str] | None = None

    extra_state_attributes_fn: Callable[[Account], dict[str, Any]] | None = None


SIMPLEFIN_SENSORS: tuple[SimpleFinSensorEntityDescription, ...] = (
    SimpleFinSensorEntityDescription(
        key="balance",
        translation_key="balance",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda account: account.balance,
        unit_fn=lambda account: account.currency,
        icon_fn=lambda account: account.inferred_account_type,
        extra_state_attributes_fn=lambda account: {
            "account_type": account.inferred_account_type.name,
        },
    ),
    SimpleFinSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda account: account.last_update,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SimpleFIN sensors for config entries."""
    simplefin_coordinator: SimpleFinDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    accounts = simplefin_coordinator.data.accounts

    for account in accounts:
        for sensor_description in SIMPLEFIN_SENSORS:
            async_add_entities(
                [
                    SimpleFinSensor(
                        coordinator=simplefin_coordinator,
                        description=sensor_description,
                        account=account,
                    )
                ],
                True,
            )


class SimpleFinSensor(SimpleFinEntity, SensorEntity):
    """Representation of a SimpleFinBalanceSensor."""

    entity_description: SimpleFinSensorEntityDescription

    @property
    def native_value(self) -> int | str | datetime | None:
        """Return the state."""
        account_data = self.coordinator.data.get_account_for_id(self._account_id)
        return self.entity_description.value_fn(account_data)

    @property
    def icon(self) -> str | None:
        """Return the currency of this account."""

        icon_fn = getattr(self.entity_description, "icon_fn", None)

        if icon_fn and callable(icon_fn):
            account_data = self.coordinator.data.get_account_for_id(self._account_id)
            return icon_fn(account_data)

        return icon_fn

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency of this account."""
        unit_fn = getattr(self.entity_description, "unit_fn", None)
        if unit_fn and callable(unit_fn):
            account_data = self.coordinator.data.get_account_for_id(self._account_id)
            return unit_fn(account_data)

        return unit_fn

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        if self.entity_description.extra_state_attributes_fn:
            return self.entity_description.extra_state_attributes_fn(
                self.coordinator.data.get_account_for_id(self._account_id)
            )
        return None
