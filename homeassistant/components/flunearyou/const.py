"""Define flunearyou constants."""
import logging

DOMAIN = "flunearyou"
LOGGER = logging.getLogger("homeassistant.components.flunearyou")

DATA_CLIENT = "client"

CATEGORY_CDC_REPORT = "cdc_report"
CATEGORY_USER_REPORT = "user_report"

TOPIC_UPDATE = "flunearyou_update"

TYPE_CDC_LEVEL = "level"
TYPE_CDC_LEVEL2 = "level2"
TYPE_USER_CHICK = "chick"
TYPE_USER_DENGUE = "dengue"
TYPE_USER_FLU = "flu"
TYPE_USER_LEPTO = "lepto"
TYPE_USER_NO_SYMPTOMS = "none"
TYPE_USER_SYMPTOMS = "symptoms"
TYPE_USER_TOTAL = "total"

SENSORS = {
    CATEGORY_CDC_REPORT: [
        (TYPE_CDC_LEVEL, "CDC Level", "mdi:biohazard", None),
        (TYPE_CDC_LEVEL2, "CDC Level 2", "mdi:biohazard", None),
    ],
    CATEGORY_USER_REPORT: [
        (TYPE_USER_CHICK, "Avian Flu Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_DENGUE, "Dengue Fever Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_FLU, "Flu Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_LEPTO, "Leptospirosis Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_NO_SYMPTOMS, "No Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_SYMPTOMS, "Flu-like Symptoms", "mdi:alert", "reports"),
        (TYPE_USER_TOTAL, "Total Symptoms", "mdi:alert", "reports"),
    ],
}
