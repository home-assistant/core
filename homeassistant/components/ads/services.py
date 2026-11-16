"""Services for the ADS integration."""

from enum import StrEnum
import logging

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


SCHEMA_SERVICE_WRITE_DATA_BY_NAME = probatio.Schema(
    {
        probatio.Required(AdsServiceArgument.ADSTYPE): probatio.Coerce(AdsType),
        probatio.Required(AdsServiceArgument.VALUE): probatio.Coerce(int),
        probatio.Required(AdsServiceArgument.ADSVAR): cv.string,
    }
)


def _handle_write_data_by_name(call: ServiceCall) -> None:
    """Write a value to the connected ADS device."""
    ads = call.hass.data[DATA_ADS]
    ads_var: str = call.data[AdsServiceArgument.ADSVAR]
    ads_type: AdsType = call.data[AdsServiceArgument.ADSTYPE]
    value: int = call.data[AdsServiceArgument.VALUE]

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
