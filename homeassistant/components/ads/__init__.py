"""Support for Automation Device Specification (ADS)."""

import logging

import pyads
import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ADS_VAR, DATA_ADS, DOMAIN
from .hub import AdsHub

_LOGGER = logging.getLogger(__name__)


# Supported Types
ADSTYPE_BOOL = "bool"
ADSTYPE_BYTE = "byte"
ADSTYPE_INT = "int"
ADSTYPE_UINT = "uint"
ADSTYPE_SINT = "sint"
ADSTYPE_USINT = "usint"
ADSTYPE_DINT = "dint"
ADSTYPE_UDINT = "udint"
ADSTYPE_WORD = "word"
ADSTYPE_DWORD = "dword"
ADSTYPE_LREAL = "lreal"
ADSTYPE_REAL = "real"
ADSTYPE_STRING = "string"
ADSTYPE_TIME = "time"
ADSTYPE_DATE = "date"
ADSTYPE_DATE_AND_TIME = "dt"
ADSTYPE_TOD = "tod"

ADS_TYPEMAP = {
    ADSTYPE_BOOL: pyads.PLCTYPE_BOOL,
    ADSTYPE_BYTE: pyads.PLCTYPE_BYTE,
    ADSTYPE_INT: pyads.PLCTYPE_INT,
    ADSTYPE_UINT: pyads.PLCTYPE_UINT,
    ADSTYPE_SINT: pyads.PLCTYPE_SINT,
    ADSTYPE_USINT: pyads.PLCTYPE_USINT,
    ADSTYPE_DINT: pyads.PLCTYPE_DINT,
    ADSTYPE_UDINT: pyads.PLCTYPE_UDINT,
    ADSTYPE_WORD: pyads.PLCTYPE_WORD,
    ADSTYPE_DWORD: pyads.PLCTYPE_DWORD,
    ADSTYPE_REAL: pyads.PLCTYPE_REAL,
    ADSTYPE_LREAL: pyads.PLCTYPE_LREAL,
    ADSTYPE_STRING: pyads.PLCTYPE_STRING,
    ADSTYPE_TIME: pyads.PLCTYPE_TIME,
    ADSTYPE_DATE: pyads.PLCTYPE_DATE,
    ADSTYPE_DATE_AND_TIME: pyads.PLCTYPE_DT,
    ADSTYPE_TOD: pyads.PLCTYPE_TOD,
}

CONF_ADS_FACTOR = "factor"
CONF_ADS_TYPE = "adstype"
CONF_ADS_VALUE = "value"


SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DEVICE): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Optional(CONF_IP_ADDRESS): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_SERVICE_WRITE_DATA_BY_NAME = vol.Schema(
    {
        vol.Required(CONF_ADS_TYPE): vol.In(
            [
                ADSTYPE_BOOL,
                ADSTYPE_BYTE,
                ADSTYPE_INT,
                ADSTYPE_UINT,
                ADSTYPE_SINT,
                ADSTYPE_USINT,
                ADSTYPE_DINT,
                ADSTYPE_UDINT,
                ADSTYPE_WORD,
                ADSTYPE_DWORD,
                ADSTYPE_REAL,
                ADSTYPE_LREAL,
                ADSTYPE_STRING,
                ADSTYPE_TIME,
                ADSTYPE_DATE,
                ADSTYPE_DATE_AND_TIME,
                ADSTYPE_TOD,
            ]
        ),
        vol.Required(CONF_ADS_VALUE): vol.Coerce(int),
        vol.Required(CONF_ADS_VAR): cv.string,
    }
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component."""

    conf = config[DOMAIN]

    net_id = conf[CONF_DEVICE]
    ip_address = conf.get(CONF_IP_ADDRESS)
    port = conf[CONF_PORT]

    client = pyads.Connection(net_id, port, ip_address)

    try:
        ads = AdsHub(client)
    except pyads.ADSError:
        _LOGGER.error(
            "Could not connect to ADS host (netid=%s, ip=%s, port=%s)",
            net_id,
            ip_address,
            port,
        )
        return False

    hass.data[DATA_ADS] = ads
    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, ads.shutdown)

    def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the connected ADS device."""
        ads_var = call.data[CONF_ADS_VAR]
        ads_type = call.data[CONF_ADS_TYPE]
        value = call.data[CONF_ADS_VALUE]

        try:
            ads.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
        except pyads.ADSError as err:
            _LOGGER.error(err)

    hass.services.register(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )

    return True
