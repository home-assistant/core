"""The enphase_envoy component."""

from pyenphase import EnvoyAuthenticationError, EnvoyAuthenticationRequired

from homeassistant.const import Platform

DOMAIN = "enphase_envoy"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

INVALID_AUTH_ERRORS = (EnvoyAuthenticationError, EnvoyAuthenticationRequired)

# ACB battery sleep is configured with a state of charge (SOC) band. The Enphase
# installer UI only offers 5% increments, so we constrain the choice to those
# tested values rather than allowing an arbitrary SOC.
ACB_SLEEP_SOC_STEP = 5
ACB_SLEEP_SOC_BANDS = [
    f"{low}-{low + ACB_SLEEP_SOC_STEP}" for low in range(0, 100, ACB_SLEEP_SOC_STEP)
]
DEFAULT_ACB_SLEEP_SOC_BAND = "95-100"

ACCESS_TOKEN_LOGIN_URL = "https://entrez.enphaseenergy.com"
CONF_MANUAL_TOKEN = "use_manual_token"

SETUP_RETRY_TIMEOUT = 50
OPERATIONAL_RETRY_TIMEOUT = 200

OPTION_DIAGNOSTICS_INCLUDE_FIXTURES = "diagnostics_include_fixtures"
OPTION_DIAGNOSTICS_INCLUDE_FIXTURES_DEFAULT_VALUE = False

OPTION_DISABLE_KEEP_ALIVE = "disable_keep_alive"
OPTION_DISABLE_KEEP_ALIVE_DEFAULT_VALUE = False
