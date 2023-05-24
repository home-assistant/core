"""Constants for the Picnic integration."""
from __future__ import annotations

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
