"""Constants for tauron."""
DOMAIN = "ais_tauron"
DEFAULT_NAME = "Tauron AmiPlus"
CONF_METER_ID = "energy_meter_id"
CONF_URL_SERVICE = "https://elicznik.tauron-dystrybucja.pl"
CONF_URL_LOGIN = "https://logowanie.tauron-dystrybucja.pl/login"
CONF_URL_CHARTS = "https://elicznik.tauron-dystrybucja.pl/index/charts"
CONF_REQUEST_HEADERS = {"cache-control": "no-cache"}
CONF_REQUEST_PAYLOAD_CHARTS = {"dane[cache]": 0}
ZONE = "zone"
CONSUMPTION_DAILY = "consumption_daily"
CONSUMPTION_MONTHLY = "consumption_monthly"
CONSUMPTION_YEARLY = "consumption_yearly"
TARIFF_G12 = "G12"
