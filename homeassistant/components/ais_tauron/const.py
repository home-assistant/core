"""Constants for tauron."""
from datetime import timedelta

DOMAIN = "ais_tauron"
DEFAULT_NAME = "Tauron AmiPlus"
DATA_TAURON_CLIENT = "data_client"
CONF_METER_ID = "energy_meter_id"
CONF_URL_SERVICE = "https://elicznik.tauron-dystrybucja.pl"
CONF_URL_LOGIN = "https://logowanie.tauron-dystrybucja.pl/login"
CONF_URL_CHARTS = "https://elicznik.tauron-dystrybucja.pl/index/charts"
CONF_REQUEST_HEADERS = {"cache-control": "no-cache"}
CONF_REQUEST_PAYLOAD_CHARTS = {"dane[cache]": 0}
TYPE_ZONE = "zone"
TYPE_CONSUMPTION_DAILY = "consumption_daily"
TYPE_CONSUMPTION_MONTHLY = "consumption_monthly"
TYPE_CONSUMPTION_YEARLY = "consumption_yearly"
TYPE_GENERATION_DAILY = "generation_daily"
TYPE_GENERATION_MONTHLY = "generation_monthly"
TYPE_GENERATION_YEARLY = "generation_yearly"
TARIFF_G12 = "G12"
SENSOR_TYPES = {
    TYPE_ZONE: [timedelta(hours=1), "kWh", "sum", ("generation", "OZEValue"), "Strefa"],
    TYPE_CONSUMPTION_DAILY: [
        timedelta(hours=1),
        "kWh",
        "sum",
        ("generation", "OZEValue"),
        "Dzienne zużycie energii",
    ],
    TYPE_CONSUMPTION_MONTHLY: [
        timedelta(hours=1),
        "kWh",
        "sum",
        ("generation", "OZEValue"),
        "Miesięczne zużycie energii",
    ],
    TYPE_CONSUMPTION_YEARLY: [
        timedelta(hours=1),
        "kWh",
        "sum",
        ("generation", "OZEValue"),
        "Roczne zużycie energii",
    ],
    TYPE_GENERATION_DAILY: [
        timedelta(hours=1),
        "kWh",
        "OZEValue",
        ("consumption", "sum"),
        "Dzienna energia oddana do sieci",
    ],
    TYPE_GENERATION_MONTHLY: [
        timedelta(hours=1),
        "kWh",
        "OZEValue",
        ("consumption", "sum"),
        "Miesięczna energia oddana do sieci",
    ],
    TYPE_GENERATION_YEARLY: [
        timedelta(hours=1),
        "kWh",
        "OZEValue",
        ("consumption", "sum"),
        "Roczna energia oddana do sieci",
    ],
}
