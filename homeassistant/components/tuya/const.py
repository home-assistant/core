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

TUYA_ENDPOINT = {
    "https://openapi.tuyaus.com": "America",
    "https://openapi.tuyacn.com": "China",
    "https://openapi.tuyaeu.com": "Europe",
    "https://openapi.tuyain.com": "India",
    "https://openapi-ueaz.tuyaus.com": "EasternAmerica",
    "https://openapi-weaz.tuyaeu.com": "WesternEurope",
}

TUYA_PROJECT_TYPE = {1: "Custom Development", 0: "Smart Home PaaS"}

TUYA_APP_TYPE = {"tuyaSmart": "TuyaSmart", "smartlife": "Smart Life"}

PLATFORMS = ["climate", "fan", "light", "scene", "switch"]
