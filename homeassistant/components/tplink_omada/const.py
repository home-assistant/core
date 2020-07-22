"""Constants for the TP-Link Omada integration."""

from datetime import timedelta

DOMAIN = "tplink_omada"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

CONF_DNSRESOLVE = "dns_resolve"
CONF_SSLVERIFY = "ssl_verify"
DEFAULT_TIMEOUT = 10
DEFAULT_SSLVERIFY = True
DEFAULT_DNSRESOLVE = False

SERVICE_WIFIACRULE = "set_wifi_access_control_rule"
SERVICE_WIFIACRULE_ATTR_RULE = "access_control_rule"

LOGIN_PATH = "/api/user/login?ajax"
CONTROLLER_PATH = "/web/v1/controller"
LOGIN_PATH = "/api/user/login"

SSID_SETTING_KEYS = [
    "accessControlRuleName",
    "bandInfo",
    "broadcast",
    "encryptionPsk",
    "id",
    "isolation",
    "name",
    "radiusAccounting",
    "radiusMacAuth",
    "rateLimit",
    "securityMode",
    "updatePeriodPsk",
    "versionPsk",
    "vlanEnable",
    "wirelessPasswordPsk",
    "wlanId",
]

SENSOR_DICT = {
    "activeUser": ["Connected clients", "clients", "mdi:account-group"],
}
SENSOR_LIST = list(SENSOR_DICT)


SENSOR_SSID_STATS_DICT = {
    "totalDownload": ["traffic_received", "bits", "mdi:download",],
    "totalUpload": ["traffic_sent", "bits", "mdi:upload",],
    "totalTraffic": ["traffic_total", "bits", "mdi:swap-vertical-bold",],
    "totalClient": ["connected_clients", "clients", "mdi:account-group",],
}
SENSOR_SSID_SETTINGS_DICT = {
    "bandInfo": "band_info",
    "isolation": "isolation",
    "vlanId": "vlan_id",
    "accessControlRuleName": "access_control_rule",
    "name": "ssid",
}

SENSOR_AP_SETTINGS_DICT = {
    "model": "Model",
    "modelVersion": "Model Version",
    "version": "Version",
    "ip": "IP",
    "mac": "Mac Address",
    "name": "Name",
}
SENSOR_AP_STATS_DICT = {
    "clientNum": ["Connected clients", "clients", "mdi:account-group",],
    "clientNum2g": ["Connected 2G clients", "clients", "mdi:account-group",],
    "clientNum5g": ["Connected 5G clients", "clients", "mdi:account-group",],
    "needUpgrade": ["Need update", "", "mdi:update",],
    "download": ["Traffic received", "bits", "mdi:download",],
    "upload": ["Traffic sent", "bits", "mdi:upload",],
}
