"""Services for the ADS integration."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import ADS_TYPEMAP, DATA_ADS, DOMAIN, AdsType


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


async def _async_handle_write_data_by_name(call: ServiceCall) -> None:
    """Write a value to the connected ADS device."""
    ads = call.hass.data[DATA_ADS]
    ads_var: str = call.data[AdsServiceArgument.ADSVAR]
    ads_type: AdsType = call.data[AdsServiceArgument.ADSTYPE]
    value: int = call.data[AdsServiceArgument.VALUE]

    # The hub logs a write the PLC refuses instead of raising it.
    await call.hass.async_add_executor_job(
        ads.write_by_name, ads_var, value, ADS_TYPEMAP[ads_type]
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the ADS services."""
    hass.services.async_register(
        DOMAIN,
        AdsService.WRITE_DATA_BY_NAME,
        _async_handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )
