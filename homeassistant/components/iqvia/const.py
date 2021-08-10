"""Define IQVIA constants."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "iqvia"

CONF_ZIP_CODE = "zip_code"

DATA_COORDINATOR = "coordinator"

TYPE_ALLERGY_FORECAST = "allergy_average_forecasted"
TYPE_ALLERGY_INDEX = "allergy_index"
TYPE_ALLERGY_OUTLOOK = "allergy_outlook"
TYPE_ALLERGY_TODAY = "allergy_index_today"
TYPE_ALLERGY_TOMORROW = "allergy_index_tomorrow"
TYPE_ASTHMA_FORECAST = "asthma_average_forecasted"
TYPE_ASTHMA_INDEX = "asthma_index"
TYPE_ASTHMA_TODAY = "asthma_index_today"
TYPE_ASTHMA_TOMORROW = "asthma_index_tomorrow"
TYPE_DISEASE_FORECAST = "disease_average_forecasted"
TYPE_DISEASE_INDEX = "disease_index"
TYPE_DISEASE_TODAY = "disease_index_today"

SENSORS = {
    TYPE_ALLERGY_FORECAST: ("Allergy Index: Forecasted Average", "mdi:flower"),
    TYPE_ALLERGY_TODAY: ("Allergy Index: Today", "mdi:flower"),
    TYPE_ALLERGY_TOMORROW: ("Allergy Index: Tomorrow", "mdi:flower"),
    TYPE_ASTHMA_FORECAST: ("Asthma Index: Forecasted Average", "mdi:flower"),
    TYPE_ASTHMA_TODAY: ("Asthma Index: Today", "mdi:flower"),
    TYPE_ASTHMA_TOMORROW: ("Asthma Index: Tomorrow", "mdi:flower"),
    TYPE_DISEASE_FORECAST: ("Cold & Flu: Forecasted Average", "mdi:snowflake"),
    TYPE_DISEASE_TODAY: ("Cold & Flu Index: Today", "mdi:pill"),
}
