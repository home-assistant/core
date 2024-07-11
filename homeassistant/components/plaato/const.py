"""Const for Plaato."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "plaato"
PLAATO_DEVICE_SENSORS = "sensors"
PLAATO_DEVICE_ATTRS = "attrs"
SENSOR_SIGNAL = f"{DOMAIN}_%s_%s"

CONF_USE_WEBHOOK = "use_webhook"
CONF_DEVICE_TYPE = "device_type"
CONF_DEVICE_NAME = "device_name"
CONF_CLOUDHOOK = "cloudhook"
PLACEHOLDER_WEBHOOK_URL = "webhook_url"
PLACEHOLDER_DOCS_URL = "docs_url"
PLACEHOLDER_DEVICE_TYPE = "device_type"
PLACEHOLDER_DEVICE_NAME = "device_name"
DOCS_URL = "https://www.home-assistant.io/integrations/plaato/"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
SENSOR_DATA = "sensor_data"
COORDINATOR = "coordinator"
DEVICE = "device"
DEVICE_NAME = "device_name"
DEVICE_TYPE = "device_type"
DEVICE_ID = "device_id"
UNDO_UPDATE_LISTENER = "undo_update_listener"
DEFAULT_SCAN_INTERVAL = 5
MIN_UPDATE_INTERVAL = timedelta(minutes=1)

EXTRA_STATE_ATTRIBUTES = {
    "beer_name": "beer_name",
    "keg_date": "keg_date",
    "mode": "mode",
    "original_gravity": "original_gravity",
    "final_gravity": "final_gravity",
    "alcohol_by_volume": "alcohol_by_volume",
}
