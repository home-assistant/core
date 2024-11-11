"""Support for Automation Device Specification (ADS)."""

from collections.abc import Mapping
import logging
from typing import Any

import pyads
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
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

# YAML Configuration Schema (to allow setup from configuration.yaml)
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component with optional YAML configuration."""
    # Check if configuration exists in YAML and set it up accordingly
    if DOMAIN not in config:
        return True  # Skip setup if no YAML configuration is present

    conf = config[DOMAIN]
    return await async_setup_ads_integration(hass, conf)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ADS from a config entry created via the GUI."""
    return await async_setup_ads_integration(hass, entry.data)


async def async_setup_ads_integration(
    hass: HomeAssistant, config: Mapping[str, Any]
) -> bool:
    """Set up common components for both YAML and config entry setups."""
    net_id = config[CONF_DEVICE]
    ip_address = config.get(CONF_IP_ADDRESS)
    port = config[CONF_PORT]

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
    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, ads.shutdown)

    async def handle_write_data_by_name(call: ServiceCall) -> None:
        """Write a value to the connected ADS device."""
        ads_var: str = call.data[CONF_ADS_VAR]
        ads_type: AdsType = call.data[CONF_ADS_TYPE]
        value: int = call.data[CONF_ADS_VALUE]

        try:
            ads.write_by_name(ads_var, value, ADS_TYPEMAP[ads_type])
        except pyads.ADSError as err:
            _LOGGER.error(err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        handle_write_data_by_name,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the ADS entry."""
    _LOGGER.debug("Unloading ADS entry: %s", entry.entry_id)

    # Check if the ADS data is available
    if DATA_ADS in hass.data:
        ads_data = hass.data[DATA_ADS]
        if ads_data:
            _LOGGER.debug("Shutting down ADS connection for %s", entry.entry_id)
            await ads_data.shutdown()
        else:
            _LOGGER.warning("ADS data is None for %s during unload", entry.entry_id)

        # Clean up the data
        del hass.data[DATA_ADS]
    else:
        _LOGGER.warning("No ADS data found in hass.data during unload")

    return True
