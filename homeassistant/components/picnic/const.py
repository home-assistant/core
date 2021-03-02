"""Constants for the Picnic integration."""
from homeassistant.const import DEVICE_CLASS_TIMESTAMP, CURRENCY_EURO

DOMAIN = "picnic"

CONF_API = "api"
CONF_COORDINATOR = "coordinator"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY_CODE = "country_code"

COUNTRY_CODES = ["NL", "DE", "BE"]
ATTRIBUTION = "picnic.app"
ADDRESS = "address"

SENSOR_COMPLETED_DELIVERIES = "completed_deliveries"
SENSOR_TOTAL_DELIVERIES = "total_deliveries"
SENSOR_CART_ITEMS_COUNT = "cart_items_count"
SENSOR_CART_TOTAL_PRICE = "cart_total_price"
SENSOR_SELECTED_SLOT_START = "selected_slot_start"
SENSOR_SELECTED_SLOT_END = "selected_slot_end"
SENSOR_SELECTED_SLOT_MAX_ODER_TIME = "selected_slot_max_order_time"
SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE = "selected_slot_min_order_value"
SENSOR_LAST_ORDER_SLOT_START = "last_order_slot_start"
SENSOR_LAST_ORDER_SLOT_END = "last_order_slot_end"
SENSOR_LAST_ORDER_STATUS = "last_order_status"
SENSOR_LAST_ORDER_DELIVERY_TIME = "last_order_delivery_time"
SENSOR_LAST_ORDER_TOTAL_PRICE = "last_order_total_price"

SENSOR_TYPES = {
    SENSOR_COMPLETED_DELIVERIES: {
        "class": None,
        "unit": None,
        "icon": "mdi:truck-delivery"
    },
    SENSOR_TOTAL_DELIVERIES: {
        "class": None,
        "unit": None,
        "icon": "mdi:truck-delivery"
    },
    SENSOR_CART_ITEMS_COUNT: {
        "class": None,
        "unit": None,
        "icon": "mdi:format-list-numbered"
    },
    SENSOR_CART_TOTAL_PRICE: {
        "class": None,
        "unit": CURRENCY_EURO,
        "icon": "mdi:currency-eur"
    },
    SENSOR_SELECTED_SLOT_START: {
        "class": DEVICE_CLASS_TIMESTAMP,
        "unit": None,
        "icon": "mdi:clock-start"
    },
    SENSOR_SELECTED_SLOT_END: {
        "class": DEVICE_CLASS_TIMESTAMP,
        "unit": None,
        "icon": "mdi:clock-end"
    },
    SENSOR_SELECTED_SLOT_MAX_ODER_TIME: {
        "class": DEVICE_CLASS_TIMESTAMP,
        "unit": None,
        "icon": "mdi:clock-alert-outline"
    },
    SENSOR_SELECTED_SLOT_MIN_ORDER_VALUE: {
        "class": None,
        "unit": CURRENCY_EURO,
        "icon": "mdi:currency-eur"
    },
    SENSOR_LAST_ORDER_SLOT_START: {
        "class": DEVICE_CLASS_TIMESTAMP,
        "unit": None,
        "icon": "mdi:clock-start"
    },
    SENSOR_LAST_ORDER_SLOT_END: {
        "class": DEVICE_CLASS_TIMESTAMP,
        "unit": None,
        "icon": "mdi:clock-end"
    },
    SENSOR_LAST_ORDER_STATUS: {
        "class": None,
        "unit": None,
        "icon": "mdi:list-status"
    },
    SENSOR_LAST_ORDER_DELIVERY_TIME: {
        "class": DEVICE_CLASS_TIMESTAMP,
        "unit": None,
        "icon": "mdi:timeline-clock"
    },
    SENSOR_LAST_ORDER_TOTAL_PRICE: {
        "class": None,
        "unit": CURRENCY_EURO,
        "icon": "mdi:cash-marker"
    }
}
