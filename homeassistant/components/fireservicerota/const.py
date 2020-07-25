"""Constants for the FireServiceRota integration."""

DOMAIN = "fireservicerota"
PLATFORMS = ["sensor", "binary_sensor", "switch"]

SENSOR_ENTITY_LIST = {
    "incidents": ["Incidents", "", "mdi:fire-truck", None, True],
}

BINARY_SENSOR_ENTITY_LIST = {
    "duty": ["Duty", "", "mdi:calendar", None, True],
}

SWITCH_ENTITY_LIST = {
    "incident_response": ["Incident Response", "", "mdi:forum", None, True],
}

URL_LIST = ["www.brandweerrooster.nl", "www.fireservicerota.co.uk"]
ATTRIBUTION = "Data provided by FireServiceRota"
WSS_BWRURL = "wss://{0}/cable?access_token={1}"
SIGNAL_UPDATE_INCIDENTS = "fsr_incidents_update"

NOTIFICATION_AUTH_TITLE = "FireServiceRota Error"
NOTIFICATION_AUTH_ID = "fsr_auth_notification"
