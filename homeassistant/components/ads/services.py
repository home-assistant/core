"""Services for the ADS integration."""

from collections.abc import Callable
from enum import StrEnum
import logging
from typing import Any

import probatio
import pyads

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import ADS_TYPEMAP, DATA_ADS, DOMAIN, AdsType

_LOGGER = logging.getLogger(__name__)


class AdsService(StrEnum):
    """Store keys for ADS services."""

    WRITE_DATA_BY_NAME = "write_data_by_name"


class AdsServiceArgument(StrEnum):
    """Store keys for ADS service arguments."""

    ADSVAR = "adsvar"
    ADSTYPE = "adstype"
    VALUE = "value"


# Types whose PLC representation is not an integer. Every other type is
# written as one, so a value entered as text still reaches the PLC correctly.
ADS_VALUE_VALIDATORS: dict[AdsType, Callable[[Any], Any]] = {
    # ctypes reads any non-empty string as True, so "off" has to be parsed.
    AdsType.BOOL: cv.boolean,
    AdsType.REAL: probatio.Coerce(float),
    AdsType.LREAL: probatio.Coerce(float),
    AdsType.STRING: cv.string,
}
DEFAULT_ADS_VALUE_VALIDATOR = probatio.Coerce(int)


def _coerce_value_for_ads_type(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce the value to the Python type its ADS type is written as."""
    validator = ADS_VALUE_VALIDATORS.get(
        data[AdsServiceArgument.ADSTYPE], DEFAULT_ADS_VALUE_VALIDATOR
    )
    return {
        **data,
        AdsServiceArgument.VALUE: validator(data[AdsServiceArgument.VALUE]),
    }


SCHEMA_SERVICE_WRITE_DATA_BY_NAME = probatio.Schema(
    probatio.All(
        probatio.Schema(
            {
                probatio.Required(AdsServiceArgument.ADSTYPE): probatio.Coerce(AdsType),
                probatio.Required(AdsServiceArgument.VALUE): probatio.Any(
                    bool, int, float, str
                ),
                probatio.Required(AdsServiceArgument.ADSVAR): cv.string,
            }
        ),
        _coerce_value_for_ads_type,
    )
)


def _handle_write_data_by_name(call: ServiceCall) -> None:
    """Write a value to the connected ADS device."""
    ads = call.hass.data[DATA_ADS]
    ads_var: str = call.data[AdsServiceArgument.ADSVAR]
    ads_type: AdsType = call.data[AdsServiceArgument.ADSTYPE]
    value: bool | float | str = call.data[AdsServiceArgument.VALUE]

    try:
        ads.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
    except pyads.ADSError as err:
        _LOGGER.error(err)


def setup_services(hass: HomeAssistant) -> None:
    """Register the ADS services."""
    hass.services.register(
        DOMAIN,
        AdsService.WRITE_DATA_BY_NAME,
        _handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )
