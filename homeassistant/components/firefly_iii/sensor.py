"""Sensor platform for Firefly III integration."""

from __future__ import annotations

from pyfirefly.models import Account, Category

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FireflyConfigEntry, FireflyDataUpdateCoordinator
from .entity import FireflyBaseEntity

ACCOUNT_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="account_type",
        translation_key="account",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
)

CATEGORY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="category",
        translation_key="category",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FireflyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Firefly III sensor platform."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        FireflyAccountEntity(
            coordinator=coordinator,
            entity_description=description,
            account=account,
        )
        for account in coordinator.data.accounts
        for description in ACCOUNT_SENSORS
    ]

    entities.extend(
        FireflyCategoryEntity(
            coordinator=coordinator,
            entity_description=description,
            category=category,
        )
        for category in coordinator.data.category_details
        for description in CATEGORY_SENSORS
    )

    async_add_entities(entities)


class FireflyAccountEntity(FireflyBaseEntity, SensorEntity):
    """Entity for Firefly III account."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        account: Account,
    ) -> None:
        """Initialize Firefly account entity."""
        super().__init__(coordinator, entity_description)
        self._account = account
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_description.key}_{account.id}"
        self._attr_name = account.attributes.name
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

        # Account type state doesn't go well with the icons.json. Need to fix it.
        if account.attributes.type == "expense":
            self._attr_icon = "mdi:cash-minus"
        elif account.attributes.type == "asset":
            self._attr_icon = "mdi:account-cash"
        elif account.attributes.type == "revenue":
            self._attr_icon = "mdi:cash-plus"
        elif account.attributes.type == "liability":
            self._attr_icon = "mdi:hand-coin"
        else:
            self._attr_icon = "mdi:bank"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._account.attributes.current_balance


class FireflyCategoryEntity(FireflyBaseEntity, SensorEntity):
    """Entity for Firefly III category."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        category: Category,
    ) -> None:
        """Initialize Firefly category entity."""
        super().__init__(coordinator, entity_description)
        self._category = category
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_description.key}_{category.id}"
        self._attr_name = category.attributes.name
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        spent_items = self._category.attributes.spent or []
        earned_items = self._category.attributes.earned or []

        spent = sum(float(item.sum) for item in spent_items if item.sum is not None)
        earned = sum(float(item.sum) for item in earned_items if item.sum is not None)

        if spent == 0 and earned == 0:
            return None
        return spent + earned
