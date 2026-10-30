"""Definition of Picnic sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    DOMAIN,
    SENSOR_CART_ITEMS_COUNT,
    SENSOR_CART_TOTAL_PRICE,
    SENSOR_LAST_ORDER_DELIVERY_TIME,
    SENSOR_LAST_ORDER_MAX_ORDER_TIME,
    SENSOR_LAST_ORDER_SLOT_END,
    SENSOR_LAST_ORDER_SLOT_START,
    SENSOR_LAST_ORDER_STATUS,
    SENSOR_LAST_ORDER_TOTAL_PRICE,
    SENSOR_NEXT_DELIVERY_ESTIMATED_ARRIVAL,
    SENSOR_NEXT_DELIVERY_ETA_END,
    SENSOR_NEXT_DELIVERY_ETA_START,
    SENSOR_NEXT_DELIVERY_SLOT_END,
    SENSOR_NEXT_DELIVERY_SLOT_START,
    SENSOR_SELECTED_SLOT_END,
    SENSOR_SELECTED_SLOT_MAX_ORDER_TIME,
    SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE,
    SENSOR_SELECTED_SLOT_START,
)
from .coordinator import (
    LastOrderData,
    NextDeliveryData,
    PicnicConfigEntry,
    PicnicUpdateCoordinator,
)

_EMPTY_DATA_FACTORIES: dict[str, Callable[[], Any]] = {
    "next_delivery_data": NextDeliveryData,
    "last_order_data": LastOrderData,
}


@dataclass(frozen=True, kw_only=True)
class PicnicSensorEntityDescription(SensorEntityDescription):
    """Describes Picnic sensor entity."""

    data_type: Literal[
        "cart_data", "slot_data", "next_delivery_data", "last_order_data"
    ]
    value_fn: Callable[[Any], StateType | datetime]

    entity_registry_enabled_default: bool = False


SENSOR_TYPES: tuple[PicnicSensorEntityDescription, ...] = (
    PicnicSensorEntityDescription(
        key=SENSOR_CART_ITEMS_COUNT,
        translation_key=SENSOR_CART_ITEMS_COUNT,
        data_type="cart_data",
        value_fn=lambda cart: (cart.total_count or 0) if cart else 0,
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_CART_TOTAL_PRICE,
        translation_key=SENSOR_CART_TOTAL_PRICE,
        native_unit_of_measurement=CURRENCY_EURO,
        data_type="cart_data",
        value_fn=lambda cart: ((cart.total_price or 0) if cart else 0) / 100,
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_START,
        translation_key=SENSOR_SELECTED_SLOT_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="slot_data",
        value_fn=lambda slot: (
            dt_util.parse_datetime(str(slot.window_start)) if slot else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_END,
        translation_key=SENSOR_SELECTED_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="slot_data",
        value_fn=lambda slot: (
            dt_util.parse_datetime(str(slot.window_end)) if slot else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_MAX_ORDER_TIME,
        translation_key=SENSOR_SELECTED_SLOT_MAX_ORDER_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="slot_data",
        value_fn=lambda slot: (
            dt_util.parse_datetime(str(slot.cut_off_time)) if slot else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE,
        translation_key=SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE,
        native_unit_of_measurement=CURRENCY_EURO,
        data_type="slot_data",
        value_fn=lambda slot: (
            slot.minimum_order_value / 100
            if slot and slot.minimum_order_value
            else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_SLOT_START,
        translation_key=SENSOR_LAST_ORDER_SLOT_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="last_order_data",
        value_fn=lambda last_order: (
            dt_util.parse_datetime(str(last_order.delivery.slot.window_start))
            if last_order.delivery and last_order.delivery.slot
            else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_SLOT_END,
        translation_key=SENSOR_LAST_ORDER_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="last_order_data",
        value_fn=lambda last_order: (
            dt_util.parse_datetime(str(last_order.delivery.slot.window_end))
            if last_order.delivery and last_order.delivery.slot
            else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_STATUS,
        translation_key=SENSOR_LAST_ORDER_STATUS,
        data_type="last_order_data",
        value_fn=lambda last_order: (
            last_order.delivery.status if last_order.delivery else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_MAX_ORDER_TIME,
        translation_key=SENSOR_LAST_ORDER_MAX_ORDER_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="last_order_data",
        value_fn=lambda last_order: (
            dt_util.parse_datetime(str(last_order.delivery.slot.cut_off_time))
            if last_order.delivery and last_order.delivery.slot
            else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_DELIVERY_TIME,
        translation_key=SENSOR_LAST_ORDER_DELIVERY_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="last_order_data",
        value_fn=lambda last_order: dt_util.parse_datetime(
            str(last_order.delivery_time_start)
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_TOTAL_PRICE,
        translation_key=SENSOR_LAST_ORDER_TOTAL_PRICE,
        native_unit_of_measurement=CURRENCY_EURO,
        data_type="last_order_data",
        value_fn=lambda last_order: last_order.total_price / 100,
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_ETA_START,
        translation_key=SENSOR_NEXT_DELIVERY_ETA_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: dt_util.parse_datetime(
            str(next_delivery.eta_start)
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_ETA_END,
        translation_key=SENSOR_NEXT_DELIVERY_ETA_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: dt_util.parse_datetime(
            str(next_delivery.eta_end)
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_ESTIMATED_ARRIVAL,
        translation_key=SENSOR_NEXT_DELIVERY_ESTIMATED_ARRIVAL,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: (
            dt_util.utc_from_timestamp(next_delivery.estimated_arrival / 1000)
            if next_delivery.estimated_arrival
            else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_SLOT_START,
        translation_key=SENSOR_NEXT_DELIVERY_SLOT_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: (
            dt_util.parse_datetime(str(next_delivery.delivery.slot.window_start))
            if next_delivery.delivery and next_delivery.delivery.slot
            else None
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_SLOT_END,
        translation_key=SENSOR_NEXT_DELIVERY_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: (
            dt_util.parse_datetime(str(next_delivery.delivery.slot.window_end))
            if next_delivery.delivery and next_delivery.delivery.slot
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PicnicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Picnic sensor entries."""
    picnic_coordinator = config_entry.runtime_data

    # Add an entity for each sensor type
    async_add_entities(
        PicnicSensor(picnic_coordinator, config_entry, description)
        for description in SENSOR_TYPES
    )


class PicnicSensor(SensorEntity, CoordinatorEntity[PicnicUpdateCoordinator]):
    """The CoordinatorEntity subclass representing Picnic sensors."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    entity_description: PicnicSensorEntityDescription

    def __init__(
        self,
        coordinator: PicnicUpdateCoordinator,
        config_entry: PicnicConfigEntry,
        description: PicnicSensorEntityDescription,
    ) -> None:
        """Init a Picnic sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{config_entry.unique_id}.{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, cast(str, config_entry.unique_id))},
            manufacturer="Picnic",
            model=config_entry.unique_id,
        )

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        data = self.coordinator.data or {}
        data_type = self.entity_description.data_type
        if data_type in data:
            data_set = data[data_type]
        else:
            factory = _EMPTY_DATA_FACTORIES.get(data_type)
            data_set = factory() if factory else None
        return self.entity_description.value_fn(data_set)
