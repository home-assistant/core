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
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ADS_VAR, DATA_ADS, DOMAIN, AdsType
from .hub import AdsHub

_LOGGER = logging.getLogger(__name__)


ADS_TYPEMAP = {
    AdsType.BOOL: pyads.PLCTYPE_BOOL,
    AdsType.BYTE: pyads.PLCTYPE_BYTE,
    AdsType.INT: pyads.PLCTYPE_INT,
    AdsType.UINT: pyads.PLCTYPE_UINT,
    AdsType.SINT: pyads.PLCTYPE_SINT,
    AdsType.USINT: pyads.PLCTYPE_USINT,
    AdsType.DINT: pyads.PLCTYPE_DINT,
    AdsType.UDINT: pyads.PLCTYPE_UDINT,
    AdsType.WORD: pyads.PLCTYPE_WORD,
    AdsType.DWORD: pyads.PLCTYPE_DWORD,
    AdsType.REAL: pyads.PLCTYPE_REAL,
    AdsType.LREAL: pyads.PLCTYPE_LREAL,
    AdsType.STRING: pyads.PLCTYPE_STRING,
    AdsType.TIME: pyads.PLCTYPE_TIME,
    AdsType.DATE: pyads.PLCTYPE_DATE,
    AdsType.DATE_AND_TIME: pyads.PLCTYPE_DT,
    AdsType.TOD: pyads.PLCTYPE_TOD,
}

CONF_ADS_FACTOR = "factor"
CONF_ADS_TYPE = "adstype"
CONF_ADS_VALUE = "value"


SERVICE_WRITE_DATA_BY_NAME = "write_data_by_name"

TASK_WATCHDOG = "ads_connection_watchdog"

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
        vol.Required(CONF_ADS_TYPE): vol.Coerce(AdsType),
        vol.Required(CONF_ADS_VALUE): vol.Coerce(int),
        vol.Required(CONF_ADS_VAR): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component."""

    conf = config[DOMAIN]

    net_id = conf[CONF_DEVICE]
    ip_address = conf.get(CONF_IP_ADDRESS)
    port = conf[CONF_PORT]

    client = pyads.Connection(net_id, port, ip_address)

    try:
        ads = await hass.async_add_executor_job(AdsHub, client)
    except pyads.ADSError:
        _LOGGER.error(
            "Could not connect to ADS host (netid=%s, ip=%s, port=%s)",
            net_id,
            ip_address,
            port,
        )
        return False

    hass.data[DATA_ADS] = ads
    hass.async_create_background_task(ads.async_watch_connection(hass), TASK_WATCHDOG)

    async def async_shutdown(event: Event) -> None:
        """Close the connection when Home Assistant stops."""
        await hass.async_add_executor_job(ads.shutdown)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)

    def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the connected ADS device."""
        ads_var: str = call.data[CONF_ADS_VAR]
        ads_type: AdsType = call.data[CONF_ADS_TYPE]
        value: int = call.data[CONF_ADS_VALUE]

        try:
            ads.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
        except pyads.ADSError as err:
            raise HomeAssistantError(f"Error writing {ads_var}: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        handle_write_data_by_name,
        schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME,
    )

    return True
