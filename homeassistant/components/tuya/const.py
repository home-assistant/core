#!/usr/bin/env python3
"""Constants for the Tuya integration."""

DOMAIN = "tuya"

CONF_PROJECT_TYPE = "tuya_project_type"
CONF_ENDPOINT = "endpoint"
CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_REGION = "region"
CONF_COUNTRY_CODE = "country_code"
CONF_APP_TYPE = "tuya_app_type"

TUYA_DISCOVERY_NEW = "tuya_discovery_new_{}"
TUYA_DEVICE_MANAGER = "tuya_device_manager"
TUYA_HOME_MANAGER = "tuya_home_manager"
TUYA_MQTT_LISTENER = "tuya_mqtt_listener"
TUYA_HA_TUYA_MAP = "tuya_ha_tuya_map"
TUYA_HA_DEVICES = "tuya_ha_devices"

TUYA_RESPONSE_CODE = "code"
TUYA_RESPONSE_RESULT = "result"
TUYA_RESPONSE_MSG = "msg"
TUYA_RESPONSE_SUCCESS = "success"
TUYA_RESPONSE_PLATFROM_URL = "platform_url"

TUYA_HA_SIGNAL_UPDATE_ENTITY = "tuya_entry_update"

TUYA_SMART_APP = "tuyaSmart"
SMARTLIFE_APP = "smartlife"

TUYA_REGIONS = {
    "America": "https://openapi.tuyaus.com",
    "China": "https://openapi.tuyacn.com",
    "Eastern America": "https://openapi-ueaz.tuyaus.com",
    "Europe": "https://openapi.tuyaeu.com",
    "India": "https://openapi.tuyain.com",
    "Western Europe": "https://openapi-weaz.tuyaeu.com",
}

PLATFORMS = ["climate", "fan", "light", "scene", "switch"]
