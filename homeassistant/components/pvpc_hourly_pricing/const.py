"""Constant values for pvpc_hourly_pricing."""

from esios_api.const import TARIFFS
import probatio

DOMAIN = "pvpc_hourly_pricing"

ATTR_POWER = "power"
ATTR_POWER_P3 = "power_p3"
ATTR_TARIFF = "tariff"
DEFAULT_NAME = "PVPC"
CONF_USE_API_TOKEN = "use_api_token"

VALID_POWER = probatio.All(probatio.Coerce(float), probatio.Range(min=1.0, max=15.0))
VALID_TARIFF = probatio.In(TARIFFS)
DEFAULT_TARIFF = TARIFFS[0]
