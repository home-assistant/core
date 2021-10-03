#!/usr/bin/env python3
"""Constants for the Tuya integration."""

DOMAIN = "tuya"

CONF_PROJECT_TYPE = "tuya_project_type"
CONF_ENDPOINT = "endpoint"
CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY_CODE = "country_code"
CONF_APP_TYPE = "tuya_app_type"

TUYA_DISCOVERY_NEW = "tuya_discovery_new_{}"
TUYA_DEVICE_MANAGER = "tuya_device_manager"
TUYA_HOME_MANAGER = "tuya_home_manager"
TUYA_MQTT_LISTENER = "tuya_mqtt_listener"
TUYA_HA_TUYA_MAP = "tuya_ha_tuya_map"
TUYA_HA_DEVICES = "tuya_ha_devices"

TUYA_HA_SIGNAL_UPDATE_ENTITY = "tuya_entry_update"

TUYA_PROJECT_TYPE_INDUSTY_SOLUTIONS = "Custom Development"
TUYA_PROJECT_TYPE_SMART_HOME = "Smart Home PaaS"

TUYA_PROJECT_TYPES = {
    TUYA_PROJECT_TYPE_SMART_HOME: 0,
    TUYA_PROJECT_TYPE_INDUSTY_SOLUTIONS: 1,
}

TUYA_ENDPOINTS = {
    "America": "https://openapi.tuyaus.com",
    "China": "https://openapi.tuyacn.com",
    "Europe": "https://openapi.tuyaeu.com",
    "India": "https://openapi.tuyain.com",
    "Eastern America": "https://openapi-ueaz.tuyaus.com",
    "Western Europe": "https://openapi-weaz.tuyaeu.com",
}

TUYA_APP_TYPES = {"TuyaSmart": "tuyaSmart", "Smart Life": "smartlife"}

PLATFORMS = ["climate", "fan", "light", "scene", "switch"]
