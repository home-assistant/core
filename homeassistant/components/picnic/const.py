"""Constants for the Picnic integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import CURRENCY_EURO
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

DOMAIN = "picnic"

CONF_API = "api"
CONF_COORDINATOR = "coordinator"
CONF_COUNTRY_CODE = "country_code"

SERVICE_ADD_PRODUCT_TO_CART = "add_product"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PRODUCT_ID = "product_id"
ATTR_PRODUCT_NAME = "product_name"
ATTR_AMOUNT = "amount"
ATTR_PRODUCT_IDENTIFIERS = "product_identifiers"

COUNTRY_CODES = ["NL", "DE", "BE"]
ATTRIBUTION = "Data provided by Picnic"
ADDRESS = "address"
CART_DATA = "cart_data"
SLOT_DATA = "slot_data"
NEXT_DELIVERY_DATA = "next_delivery_data"
LAST_ORDER_DATA = "last_order_data"

SENSOR_CART_ITEMS_COUNT = "cart_items_count"
SENSOR_CART_TOTAL_PRICE = "cart_total_price"
SENSOR_SELECTED_SLOT_START = "selected_slot_start"
SENSOR_SELECTED_SLOT_END = "selected_slot_end"
SENSOR_SELECTED_SLOT_MAX_ORDER_TIME = "selected_slot_max_order_time"
SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE = "selected_slot_min_order_value"
SENSOR_LAST_ORDER_SLOT_START = "last_order_slot_start"
SENSOR_LAST_ORDER_SLOT_END = "last_order_slot_end"
SENSOR_LAST_ORDER_STATUS = "last_order_status"
SENSOR_LAST_ORDER_MAX_ORDER_TIME = "last_order_max_order_time"
SENSOR_LAST_ORDER_DELIVERY_TIME = "last_order_delivery_time"
SENSOR_LAST_ORDER_TOTAL_PRICE = "last_order_total_price"
SENSOR_NEXT_DELIVERY_ETA_START = "next_delivery_eta_start"
SENSOR_NEXT_DELIVERY_ETA_END = "next_delivery_eta_end"
SENSOR_NEXT_DELIVERY_SLOT_START = "next_delivery_slot_start"
SENSOR_NEXT_DELIVERY_SLOT_END = "next_delivery_slot_end"


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
        icon="mdi:format-list-numbered",
        data_type="cart_data",
        value_fn=lambda cart: cart.get("total_count", 0),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_CART_TOTAL_PRICE,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:currency-eur",
        entity_registry_enabled_default=True,
        data_type="cart_data",
        value_fn=lambda cart: cart.get("total_price", 0) / 100,
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-start",
        entity_registry_enabled_default=True,
        data_type="slot_data",
        value_fn=lambda slot: dt_util.parse_datetime(str(slot.get("window_start"))),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-end",
        entity_registry_enabled_default=True,
        data_type="slot_data",
        value_fn=lambda slot: dt_util.parse_datetime(str(slot.get("window_end"))),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_MAX_ORDER_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-alert-outline",
        entity_registry_enabled_default=True,
        data_type="slot_data",
        value_fn=lambda slot: dt_util.parse_datetime(str(slot.get("cut_off_time"))),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE,
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
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-start",
        data_type="last_order_data",
        value_fn=lambda last_order: dt_util.parse_datetime(
            str(last_order.get("slot", {}).get("window_start"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-end",
        data_type="last_order_data",
        value_fn=lambda last_order: dt_util.parse_datetime(
            str(last_order.get("slot", {}).get("window_end"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_STATUS,
        icon="mdi:list-status",
        data_type="last_order_data",
        value_fn=lambda last_order: last_order.get("status"),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_LAST_ORDER_MAX_ORDER_TIME,
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
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:cash-marker",
        data_type="last_order_data",
        value_fn=lambda last_order: last_order.get("total_price", 0) / 100,
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_ETA_START,
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
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-start",
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: dt_util.parse_datetime(
            str(next_delivery.get("slot", {}).get("window_start"))
        ),
    ),
    PicnicSensorEntityDescription(
        key=SENSOR_NEXT_DELIVERY_SLOT_END,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-end",
        data_type="next_delivery_data",
        value_fn=lambda next_delivery: dt_util.parse_datetime(
            str(next_delivery.get("slot", {}).get("window_end"))
        ),
    ),
)
