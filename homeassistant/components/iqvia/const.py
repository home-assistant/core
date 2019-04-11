"""Define IQVIA constants."""
DOMAIN = 'iqvia'

DATA_CLIENT = 'client'
DATA_LISTENER = 'listener'

TOPIC_DATA_UPDATE = 'data_update'

TYPE_ALLERGY_FORECAST = 'allergy_average_forecasted'
TYPE_ALLERGY_HISTORIC = 'allergy_average_historical'
TYPE_ALLERGY_INDEX = 'allergy_index'
TYPE_ALLERGY_OUTLOOK = 'allergy_outlook'
TYPE_ALLERGY_TODAY = 'allergy_index_today'
TYPE_ALLERGY_TOMORROW = 'allergy_index_tomorrow'
TYPE_ALLERGY_YESTERDAY = 'allergy_index_yesterday'
TYPE_ASTHMA_FORECAST = 'asthma_average_forecasted'
TYPE_ASTHMA_HISTORIC = 'asthma_average_historical'
TYPE_ASTHMA_INDEX = 'asthma_index'
TYPE_ASTHMA_TODAY = 'asthma_index_today'
TYPE_ASTHMA_TOMORROW = 'asthma_index_tomorrow'
TYPE_ASTHMA_YESTERDAY = 'asthma_index_yesterday'
TYPE_DISEASE_FORECAST = 'disease_average_forecasted'

SENSORS = {
    TYPE_ALLERGY_FORECAST: (
        'ForecastSensor', 'Allergy Index: Forecasted Average', 'mdi:flower'),
    TYPE_ALLERGY_HISTORIC: (
        'HistoricalSensor', 'Allergy Index: Historical Average', 'mdi:flower'),
    TYPE_ALLERGY_TODAY: ('IndexSensor', 'Allergy Index: Today', 'mdi:flower'),
    TYPE_ALLERGY_TOMORROW: (
        'IndexSensor', 'Allergy Index: Tomorrow', 'mdi:flower'),
    TYPE_ALLERGY_YESTERDAY: (
        'IndexSensor', 'Allergy Index: Yesterday', 'mdi:flower'),
    TYPE_ASTHMA_TODAY: ('IndexSensor', 'Asthma Index: Today', 'mdi:flower'),
    TYPE_ASTHMA_TOMORROW: (
        'IndexSensor', 'Asthma Index: Tomorrow', 'mdi:flower'),
    TYPE_ASTHMA_YESTERDAY: (
        'IndexSensor', 'Asthma Index: Yesterday', 'mdi:flower'),
    TYPE_ASTHMA_FORECAST: (
        'ForecastSensor', 'Asthma Index: Forecasted Average', 'mdi:flower'),
    TYPE_ASTHMA_HISTORIC: (
        'HistoricalSensor', 'Asthma Index: Historical Average', 'mdi:flower'),
    TYPE_DISEASE_FORECAST: (
        'ForecastSensor', 'Cold & Flu: Forecasted Average', 'mdi:snowflake')
}
