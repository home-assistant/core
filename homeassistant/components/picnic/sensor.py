"""Definition of Picnic sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    ADDRESS,
    ATTRIBUTION,
    CONF_COORDINATOR,
    DOMAIN,
    SENSOR_CART_ITEMS_COUNT,
    SENSOR_CART_TOTAL_PRICE,
    SENSOR_LAST_ORDER_DELIVERY_TIME,
    SENSOR_LAST_ORDER_MAX_ORDER_TIME,
    SENSOR_LAST_ORDER_SLOT_END,
    SENSOR_LAST_ORDER_SLOT_START,
    SENSOR_LAST_ORDER_STATUS,
    SENSOR_LAST_ORDER_TOTAL_PRICE,
    SENSOR_NEXT_DELIVERY_ETA_END,
    SENSOR_NEXT_DELIVERY_ETA_START,
    SENSOR_NEXT_DELIVERY_SLOT_END,
    SENSOR_NEXT_DELIVERY_SLOT_START,
    SENSOR_SELECTED_SLOT_END,
    SENSOR_SELECTED_SLOT_MAX_ORDER_TIME,
    SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE,
    SENSOR_SELECTED_SLOT_START,
)


@dataclass
class PicnicRequiredKeysMixin:
    """Mixin for required keys."""

    data_type: Literal[
        "cart_data", "slot_data", "next_delivery_data", "last_order_data"
    ]
    value_fn: Callable[[Any], StateType | datetime]


@dataclass
class PicnicSensorEntityDescription(SensorEntityDescription, PicnicRequiredKeysMixin):
    """Describes Picnic sensor entity."""

    entity_registry_enabled_default: bool = False


SENSOR_TYPES: tuple[PicnicSensorEntityDescription, ...] = (
    PicnicSensorEntityDescription(
        key=SENSOR_CART_ITEMS_COUNT,
        translation_key=SENSOR_CART_ITEMS_COUNT,
        icon="mdi:format-list-numbered",
        data_type="cart_data",
        value_fn=lambda cart: cart.get("total_count", 0),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_CART_TOTAL_PRICE,
        translation_key=SENSOR_CART_TOTAL_PRICE,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:currency-eur",
        entity_registry_enabled_default=True,
        data_type="cart_data",
        value_fn=lambda cart: cart.get("total_price", 0) / 100,
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_START,
        translation_key=SENSOR_SELECTED_SLOT_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-start",
        entity_registry_enabled_default=True,
        data_type="slot_data",
        value_fn=lambda slot: dt_util.parse_datetime(str(slot.get("window_start"))),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_END,
        translation_key=SENSOR_SELECTED_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-end",
        entity_registry_enabled_default=True,
        data_type="slot_data",
        value_fn=lambda slot: dt_util.parse_datetime(str(slot.get("window_end"))),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_MAX_ORDER_TIME,
        translation_key=SENSOR_SELECTED_SLOT_MAX_ORDER_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-alert-outline",
        entity_registry_enabled_default=True,
        data_type="slot_data",
        value_fn=lambda slot: dt_util.parse_datetime(str(slot.get("cut_off_time"))),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE,
        translation_key=SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:currency-eur",
        entity_registry_enabled_default=True,
        data_type="slot_data",
        value_fn=lambda slot: (
            slot["minimum_order_value"] / 100
            if slot.get("minimum_order_value")
            else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_SLOT_START,
        translation_key=SENSOR_LAST_ORDER_SLOT_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-start",
        data_type="last_order_data",
        value_fn=lambda last_order: dt_util.parse_datetime(
            str(last_order.get("slot", {}).get("window_start"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_SLOT_END,
        translation_key=SENSOR_LAST_ORDER_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-end",
        data_type="last_order_data",
        value_fn=lambda last_order: dt_util.parse_datetime(
            str(last_order.get("slot", {}).get("window_end"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_STATUS,
        translation_key=SENSOR_LAST_ORDER_STATUS,
        icon="mdi:list-status",
        data_type="last_order_data",
        value_fn=lambda last_order: last_order.get("status"),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_MAX_ORDER_TIME,
        translation_key=SENSOR_LAST_ORDER_MAX_ORDER_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-alert-outline",
        entity_registry_enabled_default=True,
        data_type="last_order_data",
        value_fn=lambda last_order: dt_util.parse_datetime(
            str(last_order.get("slot", {}).get("cut_off_time"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_DELIVERY_TIME,
        translation_key=SENSOR_LAST_ORDER_DELIVERY_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:timeline-clock",
        entity_registry_enabled_default=True,
        data_type="last_order_data",
        value_fn=lambda last_order: dt_util.parse_datetime(
            str(last_order.get("delivery_time", {}).get("start"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_TOTAL_PRICE,
        translation_key=SENSOR_LAST_ORDER_TOTAL_PRICE,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:cash-marker",
        data_type="last_order_data",
        value_fn=lambda last_order: last_order.get("total_price", 0) / 100,
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_ETA_START,
        translation_key=SENSOR_NEXT_DELIVERY_ETA_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-start",
        entity_registry_enabled_default=True,
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: dt_util.parse_datetime(
            str(next_delivery.get("eta", {}).get("start"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_ETA_END,
        translation_key=SENSOR_NEXT_DELIVERY_ETA_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-end",
        entity_registry_enabled_default=True,
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: dt_util.parse_datetime(
            str(next_delivery.get("eta", {}).get("end"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_SLOT_START,
        translation_key=SENSOR_NEXT_DELIVERY_SLOT_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-start",
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: dt_util.parse_datetime(
            str(next_delivery.get("slot", {}).get("window_start"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_SLOT_END,
        translation_key=SENSOR_NEXT_DELIVERY_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-end",
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: dt_util.parse_datetime(
            str(next_delivery.get("slot", {}).get("window_end"))
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Picnic sensor entries."""
    picnic_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    # Add an entity for each sensor type
    async_add_entities(
        PicnicSensor(picnic_coordinator, config_entry, description)
        for description in SENSOR_TYPES
    )


class PicnicSensor(SensorEntity, CoordinatorEntity):
    """The CoordinatorEntity subclass representing Picnic sensors."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    entity_description: PicnicSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        config_entry: ConfigEntry,
        description: PicnicSensorEntityDescription,
    ) -> None:
        """Init a Picnic sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self.entity_id = f"sensor.picnic_{description.key}"

        self._attr_unique_id = f"{config_entry.unique_id}.{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, cast(str, config_entry.unique_id))},
            manufacturer="Picnic",
            model=config_entry.unique_id,
            name=f"Picnic: {coordinator.data[ADDRESS]}",
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        data_set = (
            self.coordinator.data.get(self.entity_description.data_type, {})
            if self.coordinator.data is not None
            else {}
        )
        return self.entity_description.value_fn(data_set)
