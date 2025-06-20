"""Sensor platform for Firefly III integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.components.todo import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import FireflyBaseEntity

_LOGGER = logging.getLogger(__name__)


ACCOUNT_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="account_type",
        translation_key="account",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

CATEGORY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="category",
        translation_key="category",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Firefly III sensor platform."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for account in coordinator.data.accounts:
        entities.extend(
            [
                FireflyAccountEntity(
                    coordinator=coordinator,
                    entity_description=description,
                    account=account,
                )
                for description in ACCOUNT_SENSORS
            ]
        )

    for category in coordinator.data.category_details:
        entities.extend(
            [
                FireflyCategoryEntity(
                    coordinator=coordinator,
                    entity_description=description,
                    category=category,
                )
                for description in CATEGORY_SENSORS
            ]
        )

    async_add_entities(entities)


class FireflyAccountEntity(FireflyBaseEntity, SensorEntity):
    """Entity for Firefly III account."""

    def __init__(self, coordinator, entity_description, account) -> None:
        """Initialize Firefly account entity."""
        super().__init__(coordinator, entity_description)
        self._account = account
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_description.key}_{account.id}"
        self._attr_name = account.attributes.name
        self._attr_native_unit_of_measurement = (
            coordinator.data.native_currency.attributes.code
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._account.attributes.current_balance

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes for the account entity."""
        return {
            "account_role": self._account.attributes.account_role,
            "account_type": self._account.attributes.type,
            "current_balance": self._account.attributes.current_balance,
        }


class FireflyCategoryEntity(FireflyBaseEntity, SensorEntity):
    """Entity for Firefly III category."""

    def __init__(self, coordinator, entity_description, category) -> None:
        """Initialize Firefly category entity."""
        super().__init__(coordinator, entity_description)
        self._category = category
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_description.key}_{category.id}"
        self._attr_name = category.attributes.name
        self._attr_native_unit_of_measurement = (
            coordinator.data.native_currency.attributes.code
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        spent = sum(float(item.sum) for item in self._category.attributes.spent)
        earned = sum(float(item.sum) for item in self._category.attributes.earned)
        if spent == 0 and earned == 0:
            return None
        return spent + earned
