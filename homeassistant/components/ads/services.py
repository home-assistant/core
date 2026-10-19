"""Services for the ADS integration."""

import logging

import probatio
import pyads

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ADS_TYPEMAP,
    CONF_ADS_TYPE,
    CONF_ADS_VALUE,
    CONF_ADS_VAR,
    DATA_ADS,
    DOMAIN,
    AdsType,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"

SCHEMA_SERVICE_WRITE_DATA_BY_NAME = probatio.Schema(
    {
        probatio.Required(CONF_ADS_TYPE): probatio.Coerce(AdsType),
        probatio.Required(CONF_ADS_VALUE): probatio.Coerce(int),
        probatio.Required(CONF_ADS_VAR): cv.string,
    }
)


def _handle_write_data_by_name(call: ServiceCall) -> None:
    """Write a value to the connected ADS device."""
    ads = call.hass.data[DATA_ADS]
    ads_var: str = call.data[CONF_ADS_VAR]
    ads_type: AdsType = call.data[CONF_ADS_TYPE]
    value: int = call.data[CONF_ADS_VALUE]

    try:
        ads.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
    except pyads.ADSError as err:
        _LOGGER.error(err)


def setup_services(hass: HomeAssistant) -> None:
    """Register the ADS services."""
    hass.services.register(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        _handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )
